"""
╔═══════════════════════════════════════════════════════════════════════════╗
║         NUTRICOACH AI - GRADIO UI (Works in Colab/Kaggle!)               ║
║                                                                           ║
║  No server setup needed - Gradio handles everything automatically!       ║
╚═══════════════════════════════════════════════════════════════════════════╝
"""

# STEP 1: Install Dependencies

print("📦 Installing dependencies...")
import subprocess
import sys

packages = ['google-genai', 'pandas', 'gradio']
for package in packages:
    subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-q', package])

print("✅ Dependencies installed!\n")

# 
# STEP 2: Import Libraries
# 

import json
from typing import Dict, Any, Tuple
import pandas as pd
import gradio as gr
from google import genai
from google.genai import types
from google.genai.types import Tool, FunctionDeclaration

# 
# STEP 3: Configuration
# 

# 🚨 PASTE YOUR API KEY HERE
GOOGLE_API_KEY = "YOUR_API_KEY"

if GOOGLE_API_KEY == "PASTE_YOUR_ACTUAL_API_KEY_HERE":
    print("⚠️  WARNING: Please paste your Google API key above!")
    print("Get one at: https://aistudio.google.com/app/apikey\n")
else:
    print("✅ API Key configured\n")

MODEL_NAME = "gemini-2.5-flash"

# 
# STEP 4: Nutrition Database
# 

NUTRITION_DB = pd.DataFrame([
    ["wheat_roti", 250, 8, 50, 2, "🌾"],
    ["white_rice", 130, 2, 28, 0, "🍚"],
    ["brown_rice", 112, 2, 24, 1, "🍚"],
    ["dal_cooked", 105, 8, 14, 0, "🫘"],
    ["paneer", 265, 18, 1, 20, "🧀"],
    ["egg_whole", 155, 13, 1, 11, "🥚"],
    ["chicken_breast", 165, 31, 0, 3, "🍗"],
    ["banana", 89, 1, 23, 0, "🍌"],
    ["apple", 52, 0, 14, 0, "🍎"],
    ["milk_whole", 60, 3, 5, 3, "🥛"],
    ["almonds", 579, 21, 22, 50, "🌰"],
    ["spinach", 23, 3, 4, 0, "🥬"],
    ["yogurt", 59, 10, 4, 0, "🥛"],
    ["oats", 389, 17, 66, 7, "🌾"],
], columns=["food", "calories", "protein", "carbs", "fat", "emoji"])

# 
# STEP 5: Tool Implementations
# 

def get_food_nutrition_impl(food_name: str) -> Dict[str, Any]:
    """Lookup food nutrition with fuzzy matching."""
    from difflib import get_close_matches
    
    matches = get_close_matches(
        food_name.lower(), 
        NUTRITION_DB['food'].tolist(), 
        n=1, 
        cutoff=0.5
    )
    
    if matches:
        result = NUTRITION_DB[NUTRITION_DB['food'] == matches[0]].iloc[0].to_dict()
        return {
            "found": True,
            "food": matches[0],
            "calories": int(result['calories']),
            "protein": int(result['protein']),
            "carbs": int(result['carbs']),
            "fat": int(result['fat']),
            "emoji": result['emoji']
        }
    
    return {"found": False, "error": f"Food '{food_name}' not found"}


def calculate_tdee_impl(
    weight_kg: float,
    height_cm: float,
    age: int,
    sex: str,
    activity_level: str = "moderate"
) -> Dict[str, Any]:
    """Calculate TDEE using Mifflin-St Jeor equation."""
    bmr = (10 * weight_kg) + (6.25 * height_cm) - (5 * age)
    bmr = bmr + 5 if sex.lower() == 'male' else bmr - 161
    
    multipliers = {
        "sedentary": 1.2,
        "light": 1.375,
        "moderate": 1.55,
        "active": 1.725,
        "very_active": 1.9
    }
    
    multiplier = multipliers.get(activity_level.lower(), 1.55)
    tdee = int(bmr * multiplier)
    
    return {
        "bmr": int(bmr),
        "tdee": tdee,
        "activity_level": activity_level,
        "multiplier": multiplier
    }

# 
# STEP 6: ADK Function Declarations
# 

nutrition_tools = Tool(function_declarations=[
    FunctionDeclaration(
        name="get_food_nutrition",
        description="Get nutritional info for a food item",
        parameters={
            "type": "object",
            "properties": {
                "food_name": {"type": "string", "description": "Name of food"}
            },
            "required": ["food_name"]
        }
    ),
    FunctionDeclaration(
        name="calculate_tdee",
        description="Calculate daily calorie needs",
        parameters={
            "type": "object",
            "properties": {
                "weight_kg": {"type": "number"},
                "height_cm": {"type": "number"},
                "age": {"type": "integer"},
                "sex": {"type": "string"},
                "activity_level": {"type": "string", "default": "moderate"}
            },
            "required": ["weight_kg", "height_cm", "age", "sex"]
        }
    )
])

# 
# STEP 7: Multi-Agent System
# 

class NutriCoachAI:
    """Multi-agent nutrition system with ADK."""
    
    def __init__(self, api_key: str):
        self.client = genai.Client(api_key=api_key)
    
    def _execute_tool(self, tool_name: str, args: Dict) -> Any:
        """Execute tool calls."""
        if tool_name == "get_food_nutrition":
            return get_food_nutrition_impl(**args)
        elif tool_name == "calculate_tdee":
            return calculate_tdee_impl(**args)
        return {"error": "Unknown tool"}
    
    def analyze_meal(self, meal_input: str) -> Dict:
        """Agent 1: Nutrition Analyst."""
        system_instruction = """You are a Nutrition Analyst. 
Parse the meal, use get_food_nutrition for each food item, calculate totals.
Return ONLY JSON: {"total_calories": N, "total_protein": N, "total_carbs": N, 
"total_fats": N, "foods": [{"name": "...", "calories": N, "protein": N, 
"carbs": N, "fat": N, "emoji": "..."}]}"""
        
        messages = [
            types.Content(role="user", parts=[types.Part(text=f"Analyze: {meal_input}")])
        ]
        
        response = self.client.models.generate_content(
            model=MODEL_NAME,
            contents=messages,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                tools=[nutrition_tools],
                temperature=0.1
            )
        )
        
        # Handle function calls
        for candidate in response.candidates:
            for part in candidate.content.parts:
                if hasattr(part, 'function_call') and part.function_call:
                    fc = part.function_call
                    result = self._execute_tool(fc.name, dict(fc.args))
                    
                    messages.append(candidate.content)
                    messages.append(types.Content(
                        role="user",
                        parts=[types.Part(
                            function_response=types.FunctionResponse(
                                name=fc.name,
                                response=result
                            )
                        )]
                    ))
                    
                    response = self.client.models.generate_content(
                        model=MODEL_NAME,
                        contents=messages,
                        config=types.GenerateContentConfig(
                            system_instruction=system_instruction,
                            tools=[nutrition_tools],
                            temperature=0.1
                        )
                    )
        
        # Parse JSON response
        try:
            text = response.text.replace("```json", "").replace("```", "").strip()
            return json.loads(text)
        except Exception as e:
            print(f"Parse error: {e}")
            return {
                "total_calories": 0,
                "total_protein": 0,
                "total_carbs": 0,
                "total_fats": 0,
                "foods": []
            }
    
    def get_coaching(self, analysis: Dict, profile: Dict) -> str:
        """Agent 2: Fitness Coach."""
        system_instruction = f"""You are a Fitness Coach.
User Profile: {json.dumps(profile)}
Intake: {analysis['total_calories']} cal, {analysis['total_protein']}g protein

Use calculate_tdee to find their needs, then provide 2-3 sentences of 
motivational, actionable feedback."""
        
        messages = [
            types.Content(role="user", parts=[types.Part(text="Give me feedback!")])
        ]
        
        response = self.client.models.generate_content(
            model=MODEL_NAME,
            contents=messages,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                tools=[nutrition_tools],
                temperature=0.7
            )
        )
        
        # Handle function calls
        for candidate in response.candidates:
            for part in candidate.content.parts:
                if hasattr(part, 'function_call') and part.function_call:
                    fc = part.function_call
                    result = self._execute_tool(fc.name, dict(fc.args))
                    
                    messages.append(candidate.content)
                    messages.append(types.Content(
                        role="user",
                        parts=[types.Part(
                            function_response=types.FunctionResponse(
                                name=fc.name,
                                response=result
                            )
                        )]
                    ))
                    
                    response = self.client.models.generate_content(
                        model=MODEL_NAME,
                        contents=messages,
                        config=types.GenerateContentConfig(
                            system_instruction=system_instruction,
                            temperature=0.7
                        )
                    )
        
        return response.text.strip()

# Initialize agent system
agent_system = None

# 
# STEP 8: Gradio Interface Functions
# 

def analyze_meal_ui(
    meal_input: str,
    weight: float,
    height: float,
    age: int,
    sex: str,
    activity: str,
    goal: str
) -> Tuple[str, str, str]:
    """Process meal analysis and return formatted results."""
    global agent_system
    
    # Validate inputs
    if not meal_input.strip():
        return "❌ Please describe your meal!", "", ""
    
    if GOOGLE_API_KEY == "PASTE_YOUR_ACTUAL_API_KEY_HERE":
        return "❌ API Key not configured! Please set it in the code above.", "", ""
    
    # Initialize agent system
    if agent_system is None:
        agent_system = NutriCoachAI(GOOGLE_API_KEY)
    
    try:
        # Create profile
        profile = {
            "weight_kg": weight,
            "height_cm": height,
            "age": age,
            "sex": sex.lower(),
            "activity_level": activity.lower().replace(" ", "_"),
            "goal": goal.lower().replace(" ", "_")
        }
        
        # Run Agent 1: Analyst
        analysis = agent_system.analyze_meal(meal_input)
        
        # Format nutrition summary
        nutrition_summary = f"""
## 📊 Nutritional Breakdown

**Total Calories:** {analysis['total_calories']} kcal  
**Protein:** {analysis['total_protein']}g  
**Carbs:** {analysis['total_carbs']}g  
**Fats:** {analysis['total_fats']}g
"""
        
        # Format food list
        food_details = "## 🍽️ Food Items\n\n"
        if analysis.get('foods'):
            for food in analysis['foods']:
                emoji = food.get('emoji', '🍽️')
                name = food.get('name', 'Unknown')
                cal = food.get('calories', 0)
                prot = food.get('protein', 0)
                carb = food.get('carbs', 0)
                fat = food.get('fat', 0)
                
                food_details += f"**{emoji} {name.replace('_', ' ').title()}**\n"
                food_details += f"- Calories: {cal} kcal\n"
                food_details += f"- Protein: {prot}g | Carbs: {carb}g | Fats: {fat}g\n\n"
        else:
            food_details += "*No foods identified*\n"
        
        # Run Agent 2: Coach
        coaching = agent_system.get_coaching(analysis, profile)
        
        coach_feedback = f"""
## 💪 Your Coach Says:

{coaching}
"""
        
        return nutrition_summary, food_details, coach_feedback
        
    except Exception as e:
        error_msg = f"❌ Error: {str(e)}\n\nPlease check your API key and try again."
        return error_msg, "", ""

# 
# STEP 9: Build Gradio Interface

def create_ui():
    """Create beautiful Gradio interface."""
    
    with gr.Blocks(
        theme=gr.themes.Soft(
            primary_hue="purple",
            secondary_hue="blue"
        ),
        title="🍎 NutriCoach AI"
    ) as demo:
        
        # Header
        gr.Markdown("""
        # 🍎 NutriCoach AI
        ### Intelligent Multi-Agent Nutrition Analysis
        
        **Powered by:** 🤖 Gemini 2.0 | ⚡ Google ADK | 🎯 Sequential Agents
        
        Describe your meal in natural language and get instant analysis with personalized coaching!
        """)
        
        with gr.Row():
            # Left Column: Inputs
            with gr.Column(scale=1):
                gr.Markdown("## 👤 Your Profile")
                
                with gr.Row():
                    weight = gr.Number(label="Weight (kg)", value=80, minimum=30, maximum=200)
                    height = gr.Number(label="Height (cm)", value=180, minimum=100, maximum=250)
                
                with gr.Row():
                    age = gr.Number(label="Age", value=35, minimum=15, maximum=100)
                    sex = gr.Dropdown(
                        label="Sex",
                        choices=["Male", "Female"],
                        value="Male"
                    )
                
                activity = gr.Dropdown(
                    label="Activity Level",
                    choices=["Sedentary", "Light", "Moderate", "Active", "Very Active"],
                    value="Moderate"
                )
                
                goal = gr.Dropdown(
                    label="Goal",
                    choices=["Weight Loss", "Maintain", "Muscle Gain"],
                    value="Muscle Gain"
                )
                
                gr.Markdown("## 🍽️ What Did You Eat?")
                
                meal_input = gr.Textbox(
                    label="Describe your meal",
                    placeholder="Example: I ate 200g chicken breast, 2 wheat rotis, 1 banana, and drank a glass of milk",
                    lines=4
                )
                
                analyze_btn = gr.Button("🔍 Analyze My Meal", variant="primary", size="lg")
            
            # Right Column: Results
            with gr.Column(scale=1):
                gr.Markdown("## 📊 Results")
                
                nutrition_output = gr.Markdown(label="Nutrition Summary")
                food_output = gr.Markdown(label="Food Details")
                coaching_output = gr.Markdown(label="Coach Feedback")
        
        # Example inputs
        gr.Examples(
            examples=[
                ["I ate 200g chicken breast, 2 wheat rotis, 1 banana, and drank milk", 80, 180, 35, "Male", "Moderate", "Muscle Gain"],
                ["Had 2 eggs, 1 cup oats, and 1 apple for breakfast", 70, 165, 28, "Female", "Active", "Weight Loss"],
                ["Lunch was dal, rice, spinach, and paneer curry", 75, 175, 40, "Male", "Light", "Maintain"],
            ],
            inputs=[meal_input, weight, height, age, sex, activity, goal],
        )
        
        # Connect button to function
        analyze_btn.click(
            fn=analyze_meal_ui,
            inputs=[meal_input, weight, height, age, sex, activity, goal],
            outputs=[nutrition_output, food_output, coaching_output]
        )
        
        # Footer
        gr.Markdown("""
        ---
        **Built with Google's Agent Development Kit (ADK)**  
        Sequential Multi-Agent System: Analyst Agent → Coach Agent
        """)
    
    return demo


# STEP 10: Launch Application


print("="*65)
print("🚀 LAUNCHING NUTRICOACH AI")
print("="*65)

if GOOGLE_API_KEY == "PASTE_YOUR_ACTUAL_API_KEY_HERE":
    print("\n⚠️  WARNING: API Key not set!")
    print("The interface will launch, but analysis won't work until you set the key.\n")
else:
    print("\nAll systems ready!\n")

print("🌐 Gradio will create a public URL automatically")
print("📱 Access the interface from the link below")
print("="*65 + "\n")

# Create and launch interface
demo = create_ui()
demo.launch(
    share=True,  # Creates public URL automatically!
    debug=False,
    show_error=True
)

print("\n Interface is live!")
print("Copy the public URL above to access from anywhere!")
