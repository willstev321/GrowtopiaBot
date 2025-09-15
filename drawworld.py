from dotenv import load_dotenv
load_dotenv()
import discord
from discord.ext import commands
import aiohttp
import asyncio
import logging
import os
import io
from datetime import datetime

# Konfigurasi logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Setup bot dengan prefix command
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='?', intents=intents)

class GrowtopiaWorldBot:
    def __init__(self):
        self.base_url = "https://s3.amazonaws.com/world.growtopiagame.com/"
        self.alternative_url = "https://growtopiagame.com/worlds/"
        self.session = None
        
    async def async_init(self):
        """Inisialisasi async session dengan timeout dan retry"""
        timeout = aiohttp.ClientTimeout(total=15)
        self.session = aiohttp.ClientSession(
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            },
            timeout=timeout,
            connector=aiohttp.TCPConnector(limit=10, verify_ssl=True)
        )
    
    async def fetch_world_image(self, world_name):
        """Mengambil gambar world dari server Growtopia dan mengembalikan data gambar"""
        # Format nama world untuk URL
        formatted_name = world_name.lower().replace(' ', '').replace('-', '').strip()
        image_url = f"{self.base_url}{formatted_name}.png"
        alternative_url = f"{self.alternative_url}{formatted_name}.png"
        
        max_retries = 3
        retry_delay = 1
        
        for attempt in range(max_retries):
            try:
                # Coba URL utama pertama
                async with self.session.get(image_url) as response:
                    logger.info(f"Status response: {response.status} untuk {image_url}")
                    
                    if response.status == 200:
                        # Baca data gambar langsung dari response
                        image_data = await response.read()
                        
                        # Validasi bahwa ini adalah gambar PNG yang valid
                        if image_data[:8] == b'\x89PNG\r\n\x1a\n':
                            logger.info(f"Berhasil mengambil gambar world: {world_name}")
                            return image_data, image_url, formatted_name
                        else:
                            logger.warning(f"File bukan gambar PNG yang valid: {world_name}")
                            continue
                            
                    elif response.status == 404:
                        logger.warning(f"World tidak ditemukan di URL utama: {world_name}")
                        # Coba URL alternatif
                        async with self.session.get(alternative_url) as alt_response:
                            if alt_response.status == 200:
                                image_data = await alt_response.read()
                                if image_data[:8] == b'\x89PNG\r\n\x1a\n':
                                    logger.info(f"Berhasil mengambil gambar dari alternative URL: {world_name}")
                                    return image_data, alternative_url, formatted_name
                                else:
                                    logger.warning(f"File alternative bukan PNG yang valid: {world_name}")
                                    continue
                            else:
                                logger.warning(f"Alternative URL juga tidak bekerja: {alt_response.status}")
                                continue
                    else:
                        logger.warning(f"HTTP {response.status} untuk {image_url}, attempt {attempt + 1}")
                        if attempt < max_retries - 1:
                            await asyncio.sleep(retry_delay * (attempt + 1))
                            continue
                        return None, image_url, formatted_name
                        
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                logger.warning(f"Error fetching {image_url}, attempt {attempt + 1}: {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay * (attempt + 1))
                    continue
                return None, image_url, formatted_name
                
        return None, image_url, formatted_name

# Inisialisasi bot
world_bot = GrowtopiaWorldBot()

@bot.event
async def on_ready():
    """Event ketika bot siap"""
    try:
        await world_bot.async_init()
        logger.info(f'{bot.user} telah terhubung ke Discord!')
        await bot.change_presence(activity=discord.Game(name="?drawworld [nama_world] - Gambar world Growtopia"))
        print("✅ Bot berhasil terhubung dan siap digunakan!")
    except Exception as e:
        logger.error(f"Error in on_ready: {e}")

@bot.command(name='drawworld')
async def drawworld_command(ctx, *, world_name):
    """Command untuk menggambar world Growtopia"""
    if not world_name or len(world_name.strip()) < 2:
        await ctx.send("❌ Silakan spesifikkan nama world yang valid (minimal 2 karakter).")
        return
    
    # Typing indicator
    async with ctx.typing():
        try:
            # Dapatkan gambar world
            image_data, image_url, formatted_name = await world_bot.fetch_world_image(world_name)
            
            if not image_data:
                # Berikan informasi yang lebih spesifik tentang error
                embed = discord.Embed(
                    title=f"❌ World '{world_name.upper()}' Tidak Ditemukan",
                    description=f"Gambar world **{world_name.upper()}** tidak dapat diakses atau tidak ada.",
                    color=0xff0000,
                    timestamp=datetime.now()
                )
                embed.add_field(
                    name="🔧 Kemungkinan Penyebab",
                    value="• World belum di-render dengan `/renderworld` di Growtopia\n• World tidak ada\n• Server Growtopia sedang down",
                    inline=False
                )
                embed.add_field(
                    name="💡 Solusi",
                    value="1. Pastikan pemilik world sudah menjalankan `/renderworld`\n2. Coba world lain yang lebih populer\n3. Coba lagi beberapa saat kemudian",
                    inline=False
                )
                embed.add_field(
                    name="🌐 Contoh World Populer",
                    value="`?drawworld GROWTOPIA`, `?drawworld START`, `?drawworld BUY`",
                    inline=False
                )
                embed.set_footer(text=f"Diminta oleh {ctx.author.display_name}")
                
                await ctx.send(embed=embed)
                return
            
            # Kirim gambar langsung ke Discord
            try:
                # Menggunakan BytesIO untuk membuat file-like object dari data gambar
                image_buffer = io.BytesIO(image_data)
                
                # Buat discord.File dari BytesIO
                file = discord.File(image_buffer, filename=f"{formatted_name}.png")
                
                # Kirim gambar langsung tanpa embed (lebih reliable)
                message = await ctx.send(file=file)
                
                # Buat embed informasi terpisah
                embed = discord.Embed(
                    title=f"🌍 World: {world_name.upper()}",
                    description=f"Gambar world **{world_name.upper()}** berhasil diambil dari Growtopia",
                    color=0x00ff00,
                    timestamp=datetime.now()
                )
                embed.add_field(name="🔗 Sumber Gambar", value=f"[Link Gambar]({image_url})", inline=False)
                embed.add_field(name="👤 Diminta Oleh", value=ctx.author.mention, inline=True)
                embed.add_field(name="📅 Diambil Pada", value=datetime.now().strftime("%Y-%m-%d %H:%M:%S"), inline=True)
                
                # Kirim embed informasi
                await ctx.send(embed=embed)
                
                logger.info(f"Gambar world {world_name} berhasil dikirim ke Discord")
                
            except discord.HTTPException as e:
                logger.error(f"Error sending image to Discord: {e}")
                # Fallback: kirim URL langsung
                await ctx.send(f"📸 **Gambar World {world_name.upper()}**\n{image_url}\n*Gambar tidak dapat ditampilkan langsung, silakan klik link di atas*")
            
        except Exception as e:
            logger.error(f"Error in drawworld command: {e}")
            await ctx.send(f"❌ Terjadi error saat mengambil gambar world '{world_name}'. Silakan coba lagi nanti.")

@bot.command(name='world')
async def world_command(ctx, *, world_name):
    """Command alternatif untuk menampilkan world (lebih simple)"""
    await drawworld_command(ctx, world_name=world_name)

@bot.command(name='w')
async def w_command(ctx, *, world_name):
    """Command shortcut untuk menampilkan world"""
    await drawworld_command(ctx, world_name=world_name)

@bot.command(name='worldinfo')
async def worldinfo_command(ctx, *, world_name):
    """Command untuk menampilkan informasi tentang world"""
    async with ctx.typing():
        try:
            # Format URL world
            formatted_name = world_name.lower().replace(' ', '').replace('-', '').strip()
            image_url = f"{world_bot.base_url}{formatted_name}.png"
            alternative_url = f"{world_bot.alternative_url}{formatted_name}.png"
            
            # Buat embed dengan informasi world
            embed = discord.Embed(
                title=f"🌍 Informasi World: {world_name.upper()}",
                description=f"Informasi tentang world **{world_name.upper()}** di Growtopia",
                color=0x0099ff,
                timestamp=datetime.now()
            )
            
            embed.add_field(
                name="📊 URL Gambar Utama", 
                value=f"[{image_url}]({image_url})", 
                inline=False
            )
            
            embed.add_field(
                name="📊 URL Gambar Alternatif", 
                value=f"[{alternative_url}]({alternative_url})", 
                inline=False
            )
            
            embed.add_field(
                name="🔧 Cara Render World", 
                value="Pemilik world harus menjalankan `/renderworld` di chat game Growtopia", 
                inline=False
            )
            
            embed.add_field(
                name="🚀 Cara Lihat Gambar", 
                value=f"Ketik `?drawworld {world_name}` atau `?w {world_name}`", 
                inline=False
            )
            
            embed.set_footer(text=f"Diminta oleh {ctx.author.display_name}")
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error in worldinfo command: {e}")
            await ctx.send(f"❌ Terjadi error saat memeriksa world '{world_name}'.")

@bot.command(name='renderinfo')
async def renderinfo_command(ctx):
    """Command untuk informasi tentang render world"""
    embed = discord.Embed(
        title="🔄 Cara Render World di Growtopia",
        description="Agar gambar world dapat diakses oleh bot, pemilik world harus melakukan render terlebih dahulu.",
        color=0xff9900,
        timestamp=datetime.now()
    )
    
    embed.add_field(
        name="📋 Langkah-langkah Render",
        value="1. Login ke Growtopia\n2. Kunjungi world yang ingin di-render\n3. Ketik `/renderworld` di chat\n4. Tunggu hingga proses selesai\n5. World siap dilihat dengan bot!",
        inline=False
    )
    
    embed.add_field(
        name="⏰ Cooldown",
        value="Render world hanya bisa dilakukan sekali setiap 24 jam",
        inline=False
    )
    
    embed.add_field(
        name="🌐 Contoh World Populer",
        value="Coba: `?w GROWTOPIA`, `?w START`, `?w BUY`",
        inline=False
    )
    
    embed.set_footer(text="Informasi Render World")
    
    await ctx.send(embed=embed)

@bot.command(name='test')
async def test_command(ctx):
    """Command untuk testing bot"""
    await ctx.send("✅ Bot berfungsi dengan baik! Gunakan `?w [nama_world]` untuk melihat gambar world")

@bot.command(name='helpbot')
async def help_command(ctx):
    """Command bantuan untuk bot"""
    embed = discord.Embed(
        title="🤖 Growtopia World Bot Help",
        description="Berikut adalah daftar command yang tersedia:",
        color=0x7289da,
        timestamp=datetime.now()
    )
    
    embed.add_field(
        name="🌍 Lihat Gambar World",
        value="• `?drawworld [nama]` - Tampilkan gambar world\n• `?world [nama]` - Sama seperti drawworld\n• `?w [nama]` - Shortcut command",
        inline=False
    )
    
    embed.add_field(
        name="ℹ️ Informasi",
        value="• `?worldinfo [nama]` - Info tentang world\n• `?renderinfo` - Cara render world\n• `?helpbot` - Bantuan ini",
        inline=False
    )
    
    embed.add_field(
        name="🔧 Testing",
        value="• `?test` - Test koneksi bot",
        inline=False
    )
    
    embed.add_field(
        name="💡 Tips",
        value="Gunakan nama world tanpa spasi. Contoh: `?w BUY`, `?w GROWTOPIA`",
        inline=False
    )
    
    embed.set_footer(text=f"Diminta oleh {ctx.author.display_name}")
    
    await ctx.send(embed=embed)

@bot.event
async def on_command_error(ctx, error):
    """Menangani error command"""
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("❌ Silakan spesifikkan nama world. Contoh: `?w BUY`")
    elif isinstance(error, commands.CommandNotFound):
        await ctx.send("❌ Command tidak dikenali. Gunakan `?helpbot` untuk melihat daftar command.")
    else:
        logger.error(f"Command error: {error}")
        await ctx.send("❌ Terjadi error saat memproses command. Silakan coba lagi.")

# JALANKAN BOT DENGAN TOKEN LANGSUNG
if __name__ == "__main__":
    # TOKEN DISCORD ANDA - PASTE DI SINI
    TOKEN = "MTQxNDgzNTEzMjUzNTI3OTY1OA.G-cjv2.cBPk_DrNiOH_Knlvfm_FWbGhPcWIoza_rojWLE"
    
    print(f"🔐 Menggunakan token: {TOKEN[:10]}...{TOKEN[-10:]}")
    print("🔗 Pastikan bot sudah diinvite ke server menggunakan link:")
    print("https://discord.com/oauth2/authorize?client_id=1414835132535279658&permissions=274878032960&scope=bot")
    print("⏳ Menghubungkan ke Discord...")
    
    try:
        bot.run(TOKEN)
    except discord.LoginFailure:
        print("❌ Token tidak valid! Silakan reset token:")
        print("1. Buka https://discord.com/developers/applications")
        print("2. Pilih aplikasi bot Anda")
        print("3. Klik 'Bot' di sidebar")
        print("4. Klik 'Reset Token'")
        print("5. Copy token baru dan ganti di kode")
    except Exception as e:
        print(f"❌ Error: {e}")