import discord
from discord import app_commands
from discord.ext import commands
import requests
import os
from dotenv import load_dotenv
from database import Database
import json
import asyncio
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('discord_bot')

load_dotenv()   

intents = discord.Intents.default()
bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)
db = Database()

API_KEY = os.getenv('API_KEY')
BASE_URL = "https://dilsmmpanel.com/api/v2"  # Replace with actual API URL

def is_admin():
    async def predicate(interaction: discord.Interaction):
        if not db.is_admin_logged_in(interaction.user.id):
            await interaction.response.send_message("You must be logged in as an admin to use this command. Use `/login` first.", ephemeral=True)
            return False
        return True
    return app_commands.check(predicate)

@bot.event
async def on_ready():
    logger.info(f'Logged in as {bot.user}')
    try:
        synced = await tree.sync()
        logger.info(f"Synced {len(synced)} command(s)")
    except Exception as e:
        logger.error(f"Failed to sync commands: {e}")
    
    # Start the status update task
    asyncio.create_task(update_status())

async def update_status():
    while True:
        try:
            await bot.change_presence(
                activity=discord.Activity(
                    type=discord.ActivityType.watching,
                    name=f"the SMM panel"
                )
            )
            await asyncio.sleep(300)  # Update every 5 minutes
        except Exception as e:
            logger.error(f"Error updating status: {e}")
            await asyncio.sleep(60)   # Wait a minute before retrying

@bot.event
async def on_error(event, *args, **kwargs):
    logger.error(f"Error in {event}:", exc_info=True)

@tree.command(name="login", description="Login as admin")
@app_commands.describe(
    username="Admin username",
    password="Admin password"
)
async def login(interaction: discord.Interaction, username: str, password: str):
    success, message = db.login_admin(username, password, interaction.user.id)
    await interaction.response.send_message(message, ephemeral=True)

@tree.command(name="logout", description="Logout from admin account")
async def logout(interaction: discord.Interaction):
    db.logout_admin(interaction.user.id)
    await interaction.response.send_message("Logged out successfully", ephemeral=True)

@tree.command(name="services", description="List all available services")
@is_admin()
async def services(interaction: discord.Interaction):
    try:
        await interaction.response.defer()
        
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache'
        }
        
        response = requests.post(
            BASE_URL,
            json={
                "key": API_KEY,
                "action": "services"
            },
            headers=headers,
            timeout=30
        )
        
        print(f"Services API Response Status: {response.status_code}")
        print(f"Services API Response Text: {response.text}")
        
        if response.status_code != 200:
            await interaction.followup.send(f"API returned status code: {response.status_code}. The website might be protected by Cloudflare.", ephemeral=True)
            return
            
        if not response.text.strip():
            await interaction.followup.send("API returned empty response", ephemeral=True)
            return
            
        if "cloudflare" in response.text.lower():
            await interaction.followup.send("The website is protected by Cloudflare. Please try again later or contact the website administrator.", ephemeral=True)
            return
            
        services = response.json()
        
        # Group services by category
        services_by_category = {}
        for service in services:
            category = service.get('category', 'Uncategorized')
            if category not in services_by_category:
                services_by_category[category] = []
            services_by_category[category].append(service)
        
        # Create a view for pagination
        class ServicesView(discord.ui.View):
            def __init__(self, services_by_category):
                super().__init__(timeout=300)  # 5 minutes timeout
                self.services_by_category = services_by_category
                self.categories = list(services_by_category.keys())
                self.current_category_index = 0
                self.current_page = 0
                self.items_per_page = 10
                
            def get_current_services(self):
                current_category = self.categories[self.current_category_index]
                services = self.services_by_category[current_category]
                start = self.current_page * self.items_per_page
                end = start + self.items_per_page
                return services[start:end], current_category, len(services)
            
            def create_embed(self):
                services, category, total_services = self.get_current_services()
                total_pages = (total_services + self.items_per_page - 1) // self.items_per_page
                
                embed = discord.Embed(
                    title=f"Available Services - {category}",
                    description=f"Page {self.current_page + 1}/{total_pages}",
                    color=discord.Color.blue()
                )
                
                for service in services:
                    embed.add_field(
                        name=f"Service {service['service']}",
                        value=f"Name: {service['name']}\nType: {service['type']}\nRate: {service['rate']}\nMin: {service['min']}\nMax: {service['max']}",
                        inline=False
                    )
                
                return embed
            
            @discord.ui.button(label="◀️", style=discord.ButtonStyle.grey)
            async def previous_page(self, interaction: discord.Interaction, button: discord.ui.Button):
                services, category, total_services = self.get_current_services()
                total_pages = (total_services + self.items_per_page - 1) // self.items_per_page
                
                if self.current_page > 0:
                    self.current_page -= 1
                else:
                    # If we're on the first page, go to the previous category's last page
                    if self.current_category_index > 0:
                        self.current_category_index -= 1
                        new_category_services = self.services_by_category[self.categories[self.current_category_index]]
                        self.current_page = (len(new_category_services) + self.items_per_page - 1) // self.items_per_page - 1
                
                await interaction.response.edit_message(embed=self.create_embed(), view=self)
            
            @discord.ui.button(label="▶️", style=discord.ButtonStyle.grey)
            async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
                services, category, total_services = self.get_current_services()
                total_pages = (total_services + self.items_per_page - 1) // self.items_per_page
                
                if self.current_page < total_pages - 1:
                    self.current_page += 1
                else:
                    # If we're on the last page, go to the next category's first page
                    if self.current_category_index < len(self.categories) - 1:
                        self.current_category_index += 1
                        self.current_page = 0
                
                await interaction.response.edit_message(embed=self.create_embed(), view=self)
            
            @discord.ui.button(label="🔄", style=discord.ButtonStyle.grey)
            async def refresh(self, interaction: discord.Interaction, button: discord.ui.Button):
                await interaction.response.edit_message(embed=self.create_embed(), view=self)
        
        view = ServicesView(services_by_category)
        await interaction.followup.send(embed=view.create_embed(), view=view)
        
    except requests.exceptions.RequestException as e:
        print(f"Network Error: {str(e)}")
        await interaction.followup.send(f"Network error: {str(e)}", ephemeral=True)
    except json.JSONDecodeError as e:
        print(f"JSON Parse Error: {str(e)}")
        await interaction.followup.send(f"Invalid API response format: {str(e)}", ephemeral=True)
    except Exception as e:
        print(f"Services Error: {str(e)}")
        await interaction.followup.send(f"Error fetching services: {str(e)}", ephemeral=True)

@tree.command(name="order", description="Place a new order")
@is_admin()
@app_commands.describe(
    service_id="The service ID",
    url="The target URL",
    quantity="The quantity needed"
)
async def order(interaction: discord.Interaction, service_id: int, url: str, quantity: int):
    try:
        await interaction.response.defer()
        
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache'
        }
        
        response = requests.post(
            BASE_URL,
            json={
                "key": API_KEY,
                "action": "add",
                "service": service_id,
                "url": url,
                "quantity": quantity
            },
            headers=headers,
            timeout=30
        )
        
        print(f"Order API Response Status: {response.status_code}")
        print(f"Order API Response Text: {response.text}")
        
        if response.status_code != 200:
            await interaction.followup.send(f"API returned status code: {response.status_code}. The website might be protected by Cloudflare.", ephemeral=True)
            return
            
        if not response.text.strip():
            await interaction.followup.send("API returned empty response", ephemeral=True)
            return
            
        if "cloudflare" in response.text.lower():
            await interaction.followup.send("The website is protected by Cloudflare. Please try again later or contact the website administrator.", ephemeral=True)
            return
            
        data = response.json()
        
        if "error" in data:
            await interaction.followup.send(f"Error: {data['error']}", ephemeral=True)
            return
            
        order_id = data["order"]
        db.add_order(order_id, url, interaction.user.id)
        await interaction.followup.send(f"Order placed successfully! Order ID: {order_id}")
    except requests.exceptions.RequestException as e:
        print(f"Network Error: {str(e)}")
        await interaction.followup.send(f"Network error: {str(e)}", ephemeral=True)
    except json.JSONDecodeError as e:
        print(f"JSON Parse Error: {str(e)}")
        await interaction.followup.send(f"Invalid API response format: {str(e)}", ephemeral=True)
    except Exception as e:
        print(f"Order Error: {str(e)}")
        await interaction.followup.send(f"Error placing order: {str(e)}", ephemeral=True)

@tree.command(name="status", description="Check order status")
@is_admin()
@app_commands.describe(
    order_id="The order ID to check (leave empty to see all orders)"
)
async def status(interaction: discord.Interaction, order_id: int = None):
    try:
        await interaction.response.defer()
        
        if order_id:
            # First check if the order exists in our database
            order = db.get_order(order_id)
            if not order:
                await interaction.followup.send(f"Order {order_id} not found in database.", ephemeral=True)
                return

            headers = {
                'Content-Type': 'application/json',
                'Accept': 'application/json',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Cache-Control': 'no-cache',
                'Pragma': 'no-cache'
            }
            
            response = requests.post(
                BASE_URL,
                json={
                    "key": API_KEY,
                    "action": "status",
                    "order": order_id
                },
                headers=headers,
                timeout=30
            )
            
            print(f"Status API Response Status: {response.status_code}")
            print(f"Status API Response Text: {response.text}")
            
            if response.status_code != 200:
                await interaction.followup.send(f"API returned status code: {response.status_code}. The website might be protected by Cloudflare.", ephemeral=True)
                return
                
            if not response.text.strip():
                await interaction.followup.send("API returned empty response", ephemeral=True)
                return
                
            if "cloudflare" in response.text.lower():
                await interaction.followup.send("The website is protected by Cloudflare. Please try again later or contact the website administrator.", ephemeral=True)
                return
                
            data = response.json()
            
            if "error" in data:
                await interaction.followup.send(f"Error: {data['error']}", ephemeral=True)
                return
                
            embed = discord.Embed(title=f"Order Status - {order_id}", color=discord.Color.green())
            embed.add_field(name="Status", value=data["status"])
            embed.add_field(name="Charge", value=data["charge"])
            embed.add_field(name="Start Count", value=data["start_count"])
            embed.add_field(name="Remains", value=data["remains"])
            await interaction.followup.send(embed=embed)
        else:
            orders = db.get_all_orders()
            if not orders:
                await interaction.followup.send("No orders found.", ephemeral=True)
                return
            
            headers = {
                'Content-Type': 'application/json',
                'Accept': 'application/json',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Cache-Control': 'no-cache',
                'Pragma': 'no-cache'
            }
            
            embed = discord.Embed(title="All Orders Status", color=discord.Color.blue())
            
            for order in orders:
                try:
                    response = requests.post(
                        BASE_URL,
                        json={
                            "key": API_KEY,
                            "action": "status",
                            "order": order["order_id"]
                        },
                        headers=headers,
                        timeout=30
                    )
                    
                    if response.status_code == 200 and response.text.strip():
                        data = response.json()
                        if "error" not in data:
                            status_info = (
                                f"Status: {data['status']}\n"
                                f"Charge: {data['charge']}\n"
                                f"Start Count: {data['start_count']}\n"
                                f"Remains: {data['remains']}\n"
                                f"URL: {order['url']}\n"
                                f"Created by: <@{order['user_id']}>"
                            )
                        else:
                            status_info = f"Error: {data['error']}\nURL: {order['url']}\nCreated by: <@{order['user_id']}>"
                    else:
                        status_info = f"Failed to fetch status\nURL: {order['url']}\nCreated by: <@{order['user_id']}>"
                except Exception as e:
                    status_info = f"Error fetching status: {str(e)}\nURL: {order['url']}\nCreated by: <@{order['user_id']}>"
                
                embed.add_field(
                    name=f"Order {order['order_id']}",
                    value=status_info,
                    inline=False
                )
            
            await interaction.followup.send(embed=embed)
    except requests.exceptions.RequestException as e:
        print(f"Network Error: {str(e)}")
        await interaction.followup.send(f"Network error: {str(e)}", ephemeral=True)
    except json.JSONDecodeError as e:
        print(f"JSON Parse Error: {str(e)}")
        await interaction.followup.send(f"Invalid API response format: {str(e)}", ephemeral=True)
    except Exception as e:
        print(f"Status Error: {str(e)}")
        await interaction.followup.send(f"Error checking status: {str(e)}", ephemeral=True)

@tree.command(name="balance", description="Check account balance")
@is_admin()
async def balance(interaction: discord.Interaction):
    try:
        await interaction.response.defer()
        
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache'
        }
        
        response = requests.post(
            BASE_URL,
            json={
                "key": API_KEY,
                "action": "balance"
            },
            headers=headers,
            timeout=30
        )
        
        print(f"Balance API Response Status: {response.status_code}")
        print(f"Balance API Response Text: {response.text}")
        
        if response.status_code != 200:
            await interaction.followup.send(f"API returned status code: {response.status_code}. The website might be protected by Cloudflare.", ephemeral=True)
            return
            
        if not response.text.strip():
            await interaction.followup.send("API returned empty response", ephemeral=True)
            return
            
        if "cloudflare" in response.text.lower():
            await interaction.followup.send("The website is protected by Cloudflare. Please try again later or contact the website administrator.", ephemeral=True)
            return
            
        data = response.json()
        
        if "error" in data:
            await interaction.followup.send(f"API Error: {data['error']}", ephemeral=True)
            return
            
        embed = discord.Embed(title="Account Balance", color=discord.Color.gold())
        embed.add_field(name="Balance", value=f"{data['balance']} {data['currency']}")
        await interaction.followup.send(embed=embed)
    except requests.exceptions.RequestException as e:
        print(f"Network Error: {str(e)}")
        await interaction.followup.send(f"Network error: {str(e)}", ephemeral=True)
    except json.JSONDecodeError as e:
        print(f"JSON Parse Error: {str(e)}")
        await interaction.followup.send(f"Invalid API response format: {str(e)}", ephemeral=True)
    except Exception as e:
        print(f"Balance Error: {str(e)}")
        await interaction.followup.send(f"Error checking balance: {str(e)}", ephemeral=True)

@tree.command(name="refill", description="Request order refill")
@is_admin()
@app_commands.describe(
    order_id="The order ID to refill"
)
async def refill(interaction: discord.Interaction, order_id: int):
    try:
        await interaction.response.defer()
        
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache'
        }
        
        response = requests.post(
            BASE_URL,
            json={
                "key": API_KEY,
                "action": "refill",
                "order": order_id
            },
            headers=headers,
            timeout=30
        )
        
        print(f"Refill API Response Status: {response.status_code}")
        print(f"Refill API Response Text: {response.text}")
        
        if response.status_code != 200:
            await interaction.followup.send(f"API returned status code: {response.status_code}. The website might be protected by Cloudflare.", ephemeral=True)
            return
            
        if not response.text.strip():
            await interaction.followup.send("API returned empty response", ephemeral=True)
            return
            
        if "cloudflare" in response.text.lower():
            await interaction.followup.send("The website is protected by Cloudflare. Please try again later or contact the website administrator.", ephemeral=True)
            return
            
        data = response.json()
        
        if data["status"] == "Success":
            await interaction.followup.send(f"Refill request submitted successfully for order {order_id}")
        else:
            await interaction.followup.send(f"Error: {data.get('message', 'Unknown error')}", ephemeral=True)
    except requests.exceptions.RequestException as e:
        print(f"Network Error: {str(e)}")
        await interaction.followup.send(f"Network error: {str(e)}", ephemeral=True)
    except json.JSONDecodeError as e:
        print(f"JSON Parse Error: {str(e)}")
        await interaction.followup.send(f"Invalid API response format: {str(e)}", ephemeral=True)
    except Exception as e:
        print(f"Refill Error: {str(e)}")
        await interaction.followup.send(f"Error requesting refill: {str(e)}", ephemeral=True)

@tree.command(name="cancel", description="Cancel an order")
@is_admin()
@app_commands.describe(
    order_id="The order ID to cancel"
)
async def cancel(interaction: discord.Interaction, order_id: int):
    try:
        await interaction.response.defer()
        
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache'
        }
        
        response = requests.post(
            BASE_URL,
            json={
                "key": API_KEY,
                "action": "cancel",
                "order": order_id
            },
            headers=headers,
            timeout=30
        )
        
        print(f"Cancel API Response Status: {response.status_code}")
        print(f"Cancel API Response Text: {response.text}")
        
        if response.status_code != 200:
            await interaction.followup.send(f"API returned status code: {response.status_code}. The website might be protected by Cloudflare.", ephemeral=True)
            return
            
        if not response.text.strip():
            await interaction.followup.send("API returned empty response", ephemeral=True)
            return
            
        if "cloudflare" in response.text.lower():
            await interaction.followup.send("The website is protected by Cloudflare. Please try again later or contact the website administrator.", ephemeral=True)
            return
            
        data = response.json()
        
        if data["status"] == "Success":
            db.update_order_status(order_id, "Cancelled")
            await interaction.followup.send(f"Order {order_id} has been marked for cancellation")
        else:
            await interaction.followup.send(f"Error: {data.get('message', 'Unknown error')}", ephemeral=True)
    except requests.exceptions.RequestException as e:
        print(f"Network Error: {str(e)}")
        await interaction.followup.send(f"Network error: {str(e)}", ephemeral=True)
    except json.JSONDecodeError as e:
        print(f"JSON Parse Error: {str(e)}")
        await interaction.followup.send(f"Invalid API response format: {str(e)}", ephemeral=True)
    except Exception as e:
        print(f"Cancel Error: {str(e)}")
        await interaction.followup.send(f"Error cancelling order: {str(e)}", ephemeral=True)

if __name__ == "__main__":
    try:
        bot.run(os.getenv('DISCORD_TOKEN'))
    except Exception as e:
        logger.critical(f"Failed to start bot: {e}")
        raise 