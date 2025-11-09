from dotenv import load_dotenv
import os
from livekit import api
from flask import Flask, jsonify
from flask_cors import CORS

load_dotenv()

app = Flask(__name__)
CORS(app)

@app.route('/get-token')
def get_token():
    token = api.AccessToken(
        api_key=os.getenv('LIVEKIT_API_KEY'),
        api_secret=os.getenv('LIVEKIT_API_SECRET')
    )
    
    token.with_identity("user-" + os.urandom(4).hex())
    token.with_name("Test User")
    token.with_grants(api.VideoGrants(
        room_join=True,
        room="my-room",
        can_publish=True,
        can_subscribe=True,
    ))
    
    return jsonify({
        'token': token.to_jwt(),
        'url': os.getenv('LIVEKIT_URL')
    })

if __name__ == '__main__':
    print("Token server running on http://localhost:3000")
    app.run(port=3000, debug=False)