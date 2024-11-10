from flask import Flask, request, jsonify, Response,render_template
import asyncio
from telethon import TelegramClient, events
import threading
import queue
import os
app = Flask(__name__)
import json
# Replace these with your actual API credentials
api_id = 29925403
api_hash = '96f2ebf244dd28a8ea8becd0ebf2f316'
bot_username = '@mealschatbot'
client = TelegramClient('session_name', api_id, api_hash)

# Queue for messages to be sent to the bot
message_queue = asyncio.Queue()

# Queue for bot responses to be sent to the frontend
bot_response_queue = queue.Queue()

async def bot_interaction_loop():
    await client.start()  # Start the client

    @client.on(events.NewMessage(from_users=bot_username))
    async def handle_new_message(event):
        message_text = event.message.message
        # Put the bot response in the response queue
        bot_response_queue.put(message_text)

    # Continuously process messages from the user
    while True:
        item = await message_queue.get()
        if isinstance(item, dict) and 'text' in item:
            await client.send_message(bot_username, item['text'])
        elif isinstance(item, dict) and 'photo' in item:
            await client.send_file(bot_username, item['photo'])
        message_queue.task_done()

@app.route('/start', methods=['POST'])
async def start_conversation():
    # Check if there's a photo in the request
    if 'photo' in request.files:
        photo = request.files['photo']
        photo_path = "temp_photo.jpg"
        photo.save(photo_path)
        await message_queue.put({"photo": photo_path})
    else:
        # Assume it's a JSON payload with a message if no photo is found
        if request.is_json:
            message = request.json.get('message')
            if message:
                await message_queue.put({"text": message})
        else:
            return jsonify({"error": "Invalid request. Please send a photo or a JSON message."}), 400

    def generate():
        bot_response_queue.queue.clear()
        while True:
            message = bot_response_queue.get()  # Block until there's a new message
            if message:
                if "Combobulating" in message:
                    continue
                lines = message.split('\n', 1)  # Split the message into two parts, first line and the rest
                if len(lines) > 1:
                    message = lines[1].strip()
                yield f"data: {message}\n\n"
                bot_response_queue.task_done()  # Mark the message as processed
                break 

    return Response(generate(), mimetype="text/event-stream")

@app.route('/bot-response-stream')
def bot_response_stream():
    def generate():
        while True:
            message = bot_response_queue.get()  # Block until there's a new message
            yield f"data: {message}\n\n"

    return Response(generate(), mimetype="text/event-stream")



# Load meal data from JSON file
with open('meals_by_bmi.json', 'r') as file:
    meals_data = json.load(file)

# Function to calculate BMI category
def calculate_bmi_category(bmi):
    if bmi < 18.5:
        return "underweight"
    elif 18.5 <= bmi < 24.9:
        return "normal"
    else:
        return "overweight"

# Home route
@app.route('/')
def index():
    return render_template('index.html')

# Route to handle BMI calculation and meal recommendation
@app.route('/get-meal', methods=['POST'])
def get_meal():
    try:
        weight = float(request.form['weight'])
        height = float(request.form['height'])
        bmi = weight / ((height / 100) ** 2)  # Convert height from cm to meters
        bmi_category = calculate_bmi_category(bmi)
        
        # Get meal recommendations based on BMI category
        recommended_meals = meals_data.get(bmi_category, {})

        return jsonify({
            "bmi": round(bmi, 2),
            "category": bmi_category,
            "meals": recommended_meals
        })
    except ValueError:
        return jsonify({"error": "Invalid input. Please enter numeric values for weight and height."}), 400


def start_telegram_client():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(bot_interaction_loop())

if __name__ == "__main__":
    threading.Thread(target=start_telegram_client).start()
    app.run(debug=True, port=os.getenv("PORT", default=5000))
