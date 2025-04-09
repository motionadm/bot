from http.server import BaseHTTPRequestHandler
import json
import os
from bot import bot

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b'Bot is running!')
        return

    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        data = json.loads(post_data)
        
        # Handle any webhook events here if needed
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b'Webhook received!')
        return

# Start the bot
if __name__ == "__main__":
    bot.run(os.getenv('DISCORD_TOKEN')) 