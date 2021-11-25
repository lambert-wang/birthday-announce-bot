import asyncio
import os
import json
import re

from datetime import datetime, timedelta

import discord
from dotenv import load_dotenv

# Load API key and configuration as environment variables from file
load_dotenv()

TOKEN = os.getenv('DISCORD_TOKEN')
GUILD = os.getenv('DISCORD_GUILD')

DEFAULT_DATA_FILE = 'data.json'
DEFAULT_TIME_ZONE = -7
DEFAULT_NOTIFICATION_HOUR = 12
COMMAND_PREFIXES = ('!birthday', '!bday')

COMMAND_NONE = '''
> Please specify a command.
> Type `!bday help` for list of commands.
'''

COMMAND_HELP = '''
> 
> __**Birthdaybot Commands**__
> 
> Commands can be invoked with any of the following prefixes:
> `!birthday`, `!bday`
> 
> `[@user] DATE`
> Sets the birthday for a user on this server. User defaults to the message author if unspecified.
> `DATE` expects a date in the following formats: MM-DD (IE `07-04` or `7-4` for July 4th)
> NOTE: Please do not include your birth year for privacy reasons (It is not saved by this bot).
> Only admins can set the date for another user.
> 
> `[@user]`
> Shows the birthday for a user on this server. User defaults to the message author if unspecified.
> Only admins can show the date for another user.
> 
> `delete [@user]`
> Deletes the birthday for a user on this server. User defaults to the message author if unspecified.
> Only admins can delete the date for another user.
> 
> `upcoming`
> Shows the upcoming birthdays in the next 30 days
> 
> `help [admin]`
> Prints this message. `help admin` prints help for admin-only commands.
> 
> `about`
> Prints information about the bot
'''

COMMAND_HELP_ADMIN = '''
> 
> __**Birthdaybot Admin Commands**__
> 
> `timezone UTC(+/-)#`
> This command sets the server time zone
> Example: `timezone UTC-5` sets the time zone to US Eastern Time.
> Default: UTC-8 (US Pacific Time)
> 
> `hour HH`
> This command sets when birthdays should be notified to the server.
> It expects an hour in 24 HR format. IE 6 = 6:00 AM, 09 = 9:00 AM, 22 = 10:00 PM
> Default: Noon (12:00 PM UTC-7)
> Note: Announcements should be made near the beginning of the hour. IE 12:05-12:10
> 
> `channel`
> This command sets the birthday announcement channel to the current channel.
> Birthday bot commands will be restricted to this channel.
> Default: No announcements will be made if no channel is set.
>
> `wipe_all`
> This command wipes all user data related to the current server.
'''

COMMAND_ABOUT = '''
> 
> __**Birthday Bot**__
> 
> This bot wishes you a happy birthday!
> Version 0.0.1
> Author: Magellan#8465
> Github: github.com/lambert-wang/birthday-announce-bot
> 
> Disclaimer: This bot is under development. Please be patient with bugs and issues. Thanks!
'''

COMMAND_ADMIN_ONLY = '''
> Sorry, this command is only available for admins!
'''

COMMAND_SERVER_ONLY = '''
> Please use this command in a server channel.
'''

# load server settings and user information from data.json
data = {}
try:
    with open(DEFAULT_DATA_FILE) as data_file:
        data = json.load(data_file)
        print(data)
except:
    print('No data file found. Creating...')
    with open(DEFAULT_DATA_FILE, 'w') as data_file:
        json.dump(data, data_file)

def saveData(dataToSave, dataFileName = DEFAULT_DATA_FILE):
    with open(dataFileName, 'w') as data_file:
        json.dump(dataToSave, data_file, indent = 2)

def isAdminMessage(message):
    return message.author.guild_permissions.administrator

def isServerMessage(message):
    try:
        return message.channel.guild != None
    except:
        return False

def getGuildData(guildId):
    return data[str(guildId)]

def deleteGuildData(guildId):
    del data[str(guildId)]
    saveData(data)

def getUserData(guildId, userId):
    return data[str(guildId)]['users'][str(userId)]

def deleteUserData(guildId, userId):
    del data[str(guildId)]['users'][str(userId)]
    saveData(data)

def userMatch(string):
    return re.compile('<@!(\d+)>').match(string)

def dateMatch(string):
    dateRegex = re.compile('(\d+)[- ](\d+)').match(string)
    if dateRegex == None:
        return None

    return (int(dateRegex.group(1)), int(dateRegex.group(2)))

def getTimezone(guildData):
    try:
        return guildData['timezone']
    except KeyError:
        return DEFAULT_TIME_ZONE

def getAnnounceHour(guildData):
    try:
        return guildData['announce_hour']
    except KeyError:
        return DEFAULT_NOTIFICATION_HOUR

def getDatetimeFromBirthday(birthday, year = datetime.utcnow().year):
    return datetime(year, birthday[0], birthday[1])

class BirthdayBotClient(discord.Client):

    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True

        super(BirthdayBotClient, self).__init__(intents = intents)

    async def sampleBirthdayLoop(self):
        while True:
            await self.sampleBirthdays()

            # Sleep until 5 minutes into the next hour
            currentMinute = datetime.utcnow().minute
            sleepMinutes = 65 - currentMinute
            print('Announcements for this hour finished. waiting {} minutes\n'.format(sleepMinutes))
            await asyncio.sleep(sleepMinutes * 60)

    async def sampleBirthdays(self, forGuild = 'all'):
        if self.is_ready() == False:
            print('Client not ready. Waiting...')
            return

        for guildId, guildData in data.items():
            try:
                if guildData['channel_id'] == -1:
                    continue
            except KeyError:
                continue

            if forGuild != 'all':
                print(forGuild)
                print(guildId)
                if guildId != forGuild:
                    continue

            guild = self.get_guild(int(guildId))
            announceChannel = guild.get_channel(guildData['channel_id'])
            print('Computing announcements for guild {}'.format(guild))

            timezone = getTimezone(guildData)
            announceHour= getAnnounceHour(guildData)

            date = datetime.utcnow() + timedelta(hours = timezone)
            print(date)
            if date.hour == announceHour:
                print("Making announcements this hour")
            else:
                print("Skipping this hour")
                continue

            # Collect a list of birthday members
            birthdayPeople = []
            for userId, userData in guildData['users'].items():
                dateMatches = dateMatch(userData['date'])
                if dateMatches == None:
                    print('DATA_ERROR: Date format for user {} is invalid'.format(userId))
                    continue

                if dateMatches[0] == date.month and dateMatches[1] == date.day:
                    birthdayPeople.append(guild.get_member(int(userId)))
                    await announceChannel.send('Happy birthday to <@!{}>!'.format(userId))

    def ensureGuildDataExists(self, guild):
        try:
            getGuildData(guild.id)
        except KeyError:
            print('No data found for current guild. Creating')
            guildData = {'name': guild.name, 'users' : {}}
            data[str(guild.id)] = guildData
            saveData(data)

    def isValidChannel(self, message):
        # Always allow DMs to go through
        if isServerMessage(message) == False:
            print('Is private message')
            return True

        guild = message.channel.guild
        self.ensureGuildDataExists(guild)
        guildData = getGuildData(guild.id)

        try:
            if guildData['channel_id'] == -1:
                return True
        except:
            return True

        return guildData['channel_id'] == message.channel.id

    def setChannel(self, message):
        guild = message.channel.guild
        self.ensureGuildDataExists(guild)
        data[str(guild.id)]['channel_id'] = message.channel.id
        saveData(data)

    def setTimezone(self, message, utcOffset):
        guild = message.channel.guild
        self.ensureGuildDataExists(guild)
        data[str(guild.id)]['timezone'] = utcOffset
        saveData(data)

    def setHour(self, message, hour):
        guild = message.channel.guild
        self.ensureGuildDataExists(guild)
        data[str(guild.id)]['announce_hour'] = hour
        saveData(data)

    # expects date in the form of a tuple (month, day)
    def setBirthday(self, guild, member, date):
        self.ensureGuildDataExists(guild)
        data[str(guild.id)]['users'][str(member.id)] = {'name': member.name, 'date' : '{}-{}'.format(date[0], date[1])}
        saveData(data)

    def getBirthday(self, guild, memberId):
        self.ensureGuildDataExists(guild)
        try:
            return getUserData(guild.id, memberId)
        except KeyError:
            raise KeyError('No user data found')

    def deleteBirthday(self, guild, memberId):
        self.ensureGuildDataExists(guild)
        try:
            deleteUserData(guild.id, memberId)
        except KeyError:
            print('No data found for user while deleting.')
            
    async def on_ready(self):
        print(f'{self.user} has connected to the server.')
        self.loop.create_task(self.sampleBirthdayLoop())

    async def commandGetUserBirthday(self, channel, user):
        guild = channel.guild
        try:
            userBirthday = getUserData(guild.id, user.id)['date']
        except KeyError:
            await channel.send('> {} has no birthday set on this server!'.format(user))
            return True

        await channel.send('> {}\'s birthday is {}!'.format(user, getDatetimeFromBirthday(dateMatch(userBirthday)).strftime('%B, %d')))
        return True

    async def on_message(self, message):
        if message.author == client.user:
            return

        if message.content.startswith(COMMAND_PREFIXES):
            args = message.content.split(' ')

            #
            # !bday
            # Prints the message sender's birthday
            #
            if len(args) < 2:
                # Validate command is sent from a valid channel
                if self.isValidChannel(message) == False:
                    return

                if isServerMessage(message) == False:
                    await message.channel.send(COMMAND_SERVER_ONLY)
                    return

                return await self.commandGetUserBirthday(message.channel, message.author)

            #
            # !bday channel
            # ADMIN ONLY
            # The only command that can be run from any channel.
            # Sets the current channel as the birthday bot channel.
            #
            if args[1] == 'channel':
                if isServerMessage(message) == False:
                    await message.channel.send(COMMAND_SERVER_ONLY)
                    return

                if isAdminMessage(message) == False:
                    await message.channel.send(COMMAND_ADMIN_ONLY)
                    return

                self.setChannel(message)
                await message.channel.send('> Set current channel for Birthday announcements!')
                return

            #
            # All commands below must be sent from a valid channel
            # Valid channels include direct messages to the bot and messages sent to the
            # guild's configured channel.
            #
            if self.isValidChannel(message) == False:
                return

            #
            # !bday help
            # Prints usage information for the bot
            #
            if args[1] == 'help':
                if len(args) < 3:
                    await message.channel.send(COMMAND_HELP)
                else:
                    await message.channel.send(COMMAND_HELP_ADMIN)
                return

            #
            # !bday about
            # Prints general information for the bot as well as the current server configuration.
            #
            if args[1] == 'about':
                await message.channel.send(COMMAND_ABOUT)

                if isServerMessage(message) == True:
                    guild = message.channel.guild
                    self.ensureGuildDataExists(guild)
                    guildData = getGuildData(guild.id)
                    await message.channel.send('''
                    > 
                    > Server Info:
                    > Timezone: UTC {}
                    > Announce Hour: {}:00
                    > Registered Birthdays: {}
                    '''.format(getTimezone(guildData), getAnnounceHour(guildData), len(guildData['users'].items())))

                return

            #
            # All commands below must be sent from a Guild
            #
            if isServerMessage(message) == False:
                await message.channel.send(COMMAND_SERVER_ONLY)
                return

            #
            # !bday [user]
            # User specific commands
            #
            userMatches = userMatch(args[1])
            if userMatches != None:
                if isAdminMessage(message) == False:
                    await message.channel.send(COMMAND_ADMIN_ONLY)
                    return

                # Ensure user exists on current guild
                guild = message.channel.guild
                userId = int(userMatches.group(1))
                user = guild.get_member(userId)
                if user == None:
                    await message.channel.send('> Error: User does not exist in current server!')
                    return

                if len(args) < 3:
                    return await self.commandGetUserBirthday(message.channel, user)

                dateMatches = dateMatch(args[2])
                if dateMatches == None:
                    await message.channel.send('> Error: Invalid date format')
                    return
                
                try:
                    datetime(year = 2000, month = dateMatches[0], day = dateMatches[1])
                except TypeError:
                    await message.channel.send('> Error: Invalid date format')
                    return
                except ValueError:
                    await message.channel.send('> Error: Invalid date format')
                    return

                self.setBirthday(guild, user, dateMatches)
                await message.channel.send('> Set {}\'s birthday!'.format(user))
                return

            #
            # !bday [date]
            # Personal command for setting a birthday
            #
            dateMatches = dateMatch(args[1])
            if dateMatches != None:
                try:
                    datetime(year = 2000, month = dateMatches[0], day = dateMatches[1])
                except TypeError:
                    await message.channel.send('> Error: Invalid date format')
                    return
                except ValueError:
                    await message.channel.send('> Error: Invalid date format')
                    return

                guild = message.channel.guild
                self.setBirthday(guild, message.author, dateMatches)
                await message.channel.send('> Set {}\'s birthday!'.format(message.author))
                return

            #
            # !bday delete [user]
            # Deletes a user's birthday from the server or deletes the sender's birthday
            # if no user is specified
            #
            if args[1] == 'delete':
                guild = message.channel.guild
                if len(args) < 3:
                    self.deleteBirthday(guild, message.author.id)
                    await message.channel.send('> Deleted {}\'s birthday!'.format(message.author))
                    return

                userMatches = userMatch(args[2])
                if userMatches != None:
                    if isAdminMessage(message) == False:
                        await message.channel.send(COMMAND_ADMIN_ONLY)
                        return

                    userId = int(userMatches.group(1))
                    user = guild.get_member(userId)
                    self.deleteBirthday(guild, userId)
                    await message.channel.send('> Deleted {}\'s birthday!'.format(user))
                    return

            #
            # !bday upcoming
            # Prints upcoming birthdays
            #
            if args[1] == 'upcoming':
                guild = message.channel.guild
                guildData = getGuildData(guild.id)
                today = datetime.utcnow() + timedelta(hours = getTimezone(guildData))
                upcomingUsers = []
                for userId, userData in guildData['users'].items():
                    dateMatches = dateMatch(userData['date'])
                    if dateMatches == None:
                        print('DATA_ERROR: Date format for user {} is invalid'.format(userId))
                        continue

                    userBirthday = getDatetimeFromBirthday(dateMatches, today.year)
                    diff = userBirthday - today
                    dayDiff = diff.days
                    if dayDiff < 0:
                        userBirthday = getDatetimeFromBirthday(dateMatches, today.year + 1)
                        diff = userBirthday - today
                        dayDiff = diff.days

                    if dayDiff < 30:
                        upcomingUsers.append((guild.get_member(int(userId)), userBirthday))

                upcomingUsers.sort(key=lambda a: a[1])
                if len(upcomingUsers) == 0:
                    await message.channel.send('> No birthdays in the next 30 days.')
                else:
                    await message.channel.send('> Upcoming birthdays:')
                    for user in upcomingUsers:
                        await message.channel.send('> {}\'s birthday is {}'.format(user[0], user[1].strftime('%B, %d')))
                
                return

            # Admin only and configuration commands
            if args[1] == 'timezone':
                if isAdminMessage(message) == False:
                    await message.channel.send(COMMAND_ADMIN_ONLY)
                    return

                if len(args) < 3:
                    await message.channel.send('> Error: Command expects an argument')
                    return

                timezoneRegex = re.compile('[uU][tT][cC]([-+]\d+)').match(args[2])
                if timezoneRegex == None:
                    await message.channel.send('> Error: Invalid timezone. Please specify an UTC offset. IE `UTC-8`, `utc+10`')
                    return

                self.setTimezone(message, int(timezoneRegex.group(1)))
                await message.channel.send('> Set server timezone to UTC{}'.format(timezoneRegex.group(1)))
                return

            if args[1] == 'hour':
                if isAdminMessage(message) == False:
                    await message.channel.send(COMMAND_ADMIN_ONLY)
                    return

                if len(args) < 3:
                    await message.channel.send('> Error: Command expects an argument')
                    return

                hour = 12
                try:
                    hour = int(args[2])
                    if hour < 1 or hour > 24:
                        raise ValueError
                except:
                    await message.channel.send('> Error: Invalid hour. Please specify an integer from 1 to 24')
                    return

                self.setHour(message, hour)
                await message.channel.send('> Set birthday announce hour to {}:00'.format(hour))
                return

            if args[1] == 'wipe_all':
                if isAdminMessage(message) == False:
                    await message.channel.send(COMMAND_ADMIN_ONLY)
                    return

                deleteGuildData(message.channel.guild.id)
                await message.channel.send('> Deleted all birthday bot data for current server!')
                return

            #
            # Force announce user birthdays
            #
            if args[1] == 'announce':
                if isAdminMessage(message) == False:
                    await message.channel.send(COMMAND_ADMIN_ONLY)
                    return
                
                await self.sampleBirthdays(forGuild = message.channel.guild)
                return

            print('Received message')
            print(message.content)

client = BirthdayBotClient()
client.run(TOKEN)
