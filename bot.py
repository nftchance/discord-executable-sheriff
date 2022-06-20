import base64
import discord
import numpy as np
import os
import requests

from discord.ext import commands
from dotenv import load_dotenv
from io import BytesIO
from PIL import Image

intents = discord.Intents.all()
intents.members = True

load_dotenv()
BOT_KEY = os.getenv('BOT_KEY')

PERMITTED_ROLES = [] # role name must provided in lower case 
CHANNELS = []
EXTRA_SECURE_MODE = True
CREDIT_AUTHOR = True

bot = commands.Bot(
    command_prefix="!",
    description="CHANCES EXECUTABLE SHERIFF",
    intents=intents
)

@bot.event
async def on_ready():
    print("[Sheriff] Online.")

def is_invalid():
    return False, None

def is_valid(uri):
    return True, uri 

def is_attachment_clean(message, attachment):
    # all users are permitted unless specific roles are set
    permitted = len(PERMITTED_ROLES) == 0
    for required_role in PERMITTED_ROLES:
        if required_role in [role.name.lower() for role in message.author.roles]:
            permitted = True
    if not permitted:
        return is_invalid()
    
    # if CHANNELS is set, confirm the message is being sent it one that's been allowed
    if len(CHANNELS) != 0 and message.channel not in CHANNELS:
        return is_invalid()

    # if we can't perform our validation abort
    if not attachment.url: is_invalid()

    # if it is not one of our accepted file formats
    if attachment.url and isinstance(attachment.url, str):
        image_formats = (".png", ".jpeg", ".jpg")
        if not attachment.url.endswith(image_formats):
            return is_invalid()

    # if we want to strip the images of metadata
    if EXTRA_SECURE_MODE:
        try:
            # prepare buffer so that we don't save images
            buffer = BytesIO()

            # get image data from discord url
            response = requests.get(attachment.url)
            
            # if we can't download the image
            if response.status_code != 200: return is_invalid()

            # base64 encode the metadata
            uri = base64.b64encode(response.content)
            image = Image.open(BytesIO(base64.b64decode(uri)))

            # convert to array where metadata cannot be stored 
            # (image data only)
            image_array = np.array(image)  
            buffered_uri = Image.fromarray(image_array)

            # Handling PNGs because we don't want to ruin transparent images
            if attachment.url.endswith('.png'):
                # Get the pallete if there is one 
                # (preserves transparency)
                palette = image.getpalette()
                if palette != None:
                    buffered_uri.putpalette(palette)

                buffered_uri.save(buffer, format="PNG")

            # go on without needing any new interaction for normal pictures
            else:
                buffered_uri.save(buffer, format='JPEG')

            uri = base64.b64encode(buffer.getvalue())

            return is_valid(uri)
        except Exception as e:
            print('ERROR ENCOUNTERED: ' + e)
            return is_invalid()

    return is_invalid()

async def send_attachment_replacement(
    message, 
    attachment, 
    uri,
):
    # send the image as a replacement
    output_image = discord.File(
        BytesIO(base64.b64decode(uri)), 
        filename=attachment.filename
    )
    # send the image from our bot since a bot cannot
    # send a message as the user
    await message.channel.send(file=output_image)

    if CREDIT_AUTHOR:
        # add the appropriate caption
        caption = f"> {message.content}\n > \n" if message.content else "" 

        await message.channel.send(
            f"{caption}> - <@{message.author.id}>"
        )

@bot.event
async def on_message(message):
    # only clean images sent by a user
    if message.author != bot.user:
        # determine if the message has any attachments
        if message.attachments:
            for attachment in message.attachments:
                # make sure that every attachment is clean and safe
                clean, uri = is_attachment_clean(attachment)

                # if the image is not clean or we have a sanitized image
                if not clean or uri:
                    try:
                        await message.delete()
                    except:
                        # will fail if we have already deleted the image
                        pass

                # if we have a valid image to send, send it
                if uri:
                    await send_attachment_replacement(
                        message,
                        attachment,
                        uri
                    )

bot.run(BOT_KEY)