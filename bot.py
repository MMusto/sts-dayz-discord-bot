import os, asyncio, requests, hashlib, discord
from discord.ext import commands

TOKEN = os.environ["TOKEN"]
USER_AGENT	  = os.environ["USER_AGENT"]
CLIENT_ID	   = os.environ["CLIENT_ID"]
PLAIN_SECRET	= os.environ["PLAIN_SECRET"]
SERVER_IP		= '35.245.115.144'

HASHED_SECRET   = hashlib.sha256(PLAIN_SECRET.encode('utf-8')).hexdigest()

headers = {
	'User-Agent': USER_AGENT,
	'Client-ID': CLIENT_ID
}

payload = {
	'secret': HASHED_SECRET
}


bot = commands.Bot(command_prefix='.')

running = False
api_count = 0
stats = None
delay = 30
request = None


def parse_data(data):
	'''
	status			: BOOL  - Server Online/Offline
	gametime		: STR	- In-game time
	player_count	: INT 	- Players online
	max_players		: INT 	- Server's max players
	all_mods 		: LIST 	- All mods on the server.
	mod_count 		: INT 	- Number of mods
	misc_stats		: DICT 	= Misc. server stats

	'''
	results = dict()
	
	if data['results'] != 1:
		print("[!] Error retrieving data. (Results != 1)")
		return -1

	data = data['servers'][0]

	results['status'] = data['online']

	server = data['gameserver']

	results['gametime'] = server['environment']['gametime']

	results['player_count'] = server['players'] if results['status'] else 0

	results['max_players'] = server['max_players']

	misc_stats = dict()

	misc_stats['Time Acceleration'] 		= server['settings']['time_acceleration']
	misc_stats['Night Time Acceleration'] 	= server['settings']['night_time_acceleration']
	misc_stats['Third Person'] 				= server['settings']['third_person']
	misc_stats['Server Version']			= server['version']
	misc_stats['Map']						= server['map']
	
	results['misc_stats'] = misc_stats

	mods = server['mods']
	
	if mods['available']:
		results['mod_count'] = mods['count']
		results['all_mods'] = {mod_data['name']:mod_data['steamWorkshopId'] for mod_data in mods['list']}
	else:
		print("[!] Error: mods not available. mods['available'] = {}".format(mods['available']))
	return results
		
@bot.event
async def on_ready():
	global running
	print(bot.user.name)
	print("**********THE BOT IS READY**********")
	await bot.change_presence(status=discord.Status.dnd, activity=discord.Game("Playing DayZ"))
	if not running:
		await updater()
		running = True

async def updater():
	global running
	global delay
	global stats
	running = True
	while True:
		await update_stats()
		await asyncio.sleep(delay)

async def update_stats():
	global api_count
	global stats
	
	data = get_data()
	if (data):
		stats = parse_data(data)
		await update_channels()
		api_count += 1
	else:
		print("Error getting data from API. (function update_stats")

	return True
   
def get_data():
	global request
	global headers
	if request == None:
		request = requests.post('https://cfbackend.de/auth/login', headers=headers, json=payload)
		headers.update({
			'Authorization': 'Bearer {}'.format(request.json().get('access_token'))
		})
		if request.status_code != 200:
			print('[!] Failed to log-in: {}'.format(request.json()))
			return False
		return get_data()
	try:
		response = requests.get('https://cfbackend.de/v1/servers/' + SERVER_IP + '/ataddress', headers=headers)
		if response.status_code == 200:
			return response.json()
		else:
			print("[!] Error getting data (function get_data). Response Code = {}".format(response.status_code))
			response = None
			request = None
			return get_data()
 
	except:
		request = requests.post('https://cfbackend.de/auth/login', headers=headers, json=payload)
		headers.update({
			'Authorization': 'Bearer {}'.format(request.json().get('access_token'))
		})
		if request.status_code != 200:
			print('[!] Failed to log-in: {}'.format(request.json()))
			return False
		return get_data()
async def update_channels():
	global stats
	players_online_channel = get_channel('voice', 'players online')
	current_status_channel = get_channel('voice', 'current status')
	if players_online_channel == None or current_status_channel == None:
		print("Error: could not a stat channel")
	await players_online_channel.edit(name = "Players Online: {}/{}".format(stats['player_count'], stats['max_players']))
	status = "ONLINE" if stats['status'] else "OFFLINE"
	await current_status_channel.edit(name = "Current Status: {}".format(status))
	
@bot.command(pass_context=True)
async def force_update_stats(ctx):
	if ctx.message.author.guild_permissions.administrator:
		success = await update_stats()
		if success:
			await ctx.send("Success.")
		else:
			await ctx.send("Failed.")
	else:
		await ctx.send("Hey {}, You don't have permission to do that.".format(ctx.author.mention))
		
@bot.command(pass_context=True)
async def mods(ctx):
	global stats
	if ctx.message.author.guild_permissions.administrator:
		if stats.get('mod_count') and stats.get('all_mods'):
			embed = discord.Embed(title="Smurf Team Six DayZ Bot", description="Here's a list of all {} mods with links to their respective workshop.".format(stats['mod_count']), color=0x09dee1)
			for name, w_id in stats['all_mods'].items():
				embed.add_field(name=name, value='https://steamcommunity.com/sharedfiles/filedetails/?id={}'.format(w_id))
			await ctx.send(embed=embed)
		else:
			await ctx.send("Hey {}, The mod list wasn't found. Go complain to Justin.".format(ctx.author.mention))
	else:
		await ctx.send("Hey {}, You don't have permission to do that.".format(ctx.author.mention))
	
@bot.command(pass_context=True)
async def apicount(ctx):
	global api_count
	if ctx.message.author.guild_permissions.administrator:
		await ctx.message.delete()
		await ctx.send(">>> # API Calls = {}".format(str(api_count)), delete_after=5.0)
	else:
		await ctx.send("Hey {}, You don't have permission to do that.".format(ctx.author.mention))

@bot.command(pass_context=True)
async def stats(ctx):
	global stats
	global delay
	
	if ctx.message.author.guild_permissions.administrator:
		#await ctx.message.delete()
		embed = discord.Embed(title="Smurf Team Six DayZ Server", description="Stats are reset every {} seconds.".format(delay), color=0x09dee1)
		status = "ONLINE" if stats['status'] else "OFFLINE"
		embed.add_field(name="Server Status", value = status)
		embed.add_field(name="Player Count", value = "{}/{}".format(stats['player_count'], stats['max_players']))
		
		if stats.get('mod_count') and stats.get('all_mods'):
			embed.add_field(name= "Mod Count", value = "{} (Type .mods for more)".format(stats['mod_count']))
			
		for key, value in stats['misc_stats'].items():
			embed.add_field(name=key, value=value)
		
			
		await ctx.send(embed=embed)
	else:
		await ctx.send("Hey {}, You don't have permission to do that.".format(ctx.author.mention))
		
async def setgame(ctx, gam):
	'''Modify game played by bot is friends list/status bar'''
	if ctx.message.author.guild_permissions.administrator:
		await bot.change_presence(activity=discord.Game(name=gam))
	else:
		await ctx.send("Hey {}, You don't have permission to do that.".format(ctx.author.mention))
		
###############################################		 
#			   HELPER FUNCTIONS				  #
###############################################
#type = 'voice' or 'text'
def get_channel(typ : str, chname : str) -> "Channel":
	'''Helper function that returns Channel object from name snippet'''
	for server in bot.guilds:
		if "DayZ" in server.name:
			for channel in server.channels:
					if(str(channel.type) == typ):
							if(chname.lower() in channel.name.lower()):
									return channel
	return None


	

bot.run(TOKEN)