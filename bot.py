import os
import json
import logging
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import gspread
from google.oauth2.service_account import Credentials

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Config dari environment variables
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
SPREADSHEET_ID = os.environ.get("SPREADSHEET_ID")
GOOGLE_CREDENTIALS = os.environ.get("GOOGLE_CREDENTIALS")

# Setup Google Sheets
def get_sheet():
    creds_dict = json.loads(GOOGLE_CREDENTIALS)
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(SPREADSHEET_ID).sheet1
    return sheet

# Tambah transaksi ke sheet
def tambah_transaksi(tanggal, keterangan, kategori, jumlah, tipe):
    sheet = get_sheet()
    sheet.append_row([tanggal, keterangan, kategori, jumlah, tipe])

# Hitung total
def hitung_total():
    sheet = get_sheet()
    data = sheet.get_all_records()
    masuk = sum(row["Jumlah"] for row in data if row["Tipe"] == "Masuk")
    keluar = sum(row["Jumlah"] for row in data if row["Tipe"] == "Keluar")
    saldo = masuk - keluar
    return masuk, keluar, saldo, len(data)

# Parse pesan pengguna
def parse_pesan(text):
    text = text.lower().strip()
    
    # Kategori pengeluaran
    kategori_keluar = {
        "makan": ["makan", "minum", "kopi", "resto", "warung", "cafe", "food", "lunch", "dinner", "breakfast", "sarapan", "siang", "malam", "snack", "jajan"],
        "transport": ["bensin", "parkir", "grab", "gojek", "ojek", "bus", "angkot", "taxi", "transport", "bbm", "tol"],
        "belanja": ["belanja", "beli", "shopee", "tokopedia", "lazada", "mall", "toko"],
        "tagihan": ["listrik", "air", "internet", "wifi", "pulsa", "data", "token", "pdam"],
        "kesehatan": ["obat", "dokter", "apotek", "klinik", "rs", "rumah sakit"],
        "hiburan": ["nonton", "film", "game", "spotify", "netflix", "youtube"],
    }
    
    # Kategori pemasukan
    kategori_masuk = {
        "gaji": ["gaji", "salary", "upah"],
        "freelance": ["freelance", "proyek", "project", "kerja"],
        "transfer": ["transfer", "kirim", "terima"],
        "lainnya": ["bonus", "hadiah", "uang"],
    }

    # Cari angka di pesan
    import re
    angka = re.findall(r'\d+(?:\.\d+)?(?:k|rb|ribu|jt|juta)?', text)
    if not angka:
        return None
    
    # Konversi angka
    raw = angka[-1]
    num = float(re.sub(r'[^\d.]', '', raw))
    if 'k' in raw or 'rb' in raw or 'ribu' in raw:
        num *= 1000
    elif 'jt' in raw or 'juta' in raw:
        num *= 1000000
    jumlah = int(num)

    # Tentukan tipe dan kategori
    tipe = "Keluar"
    kategori = "Lainnya"
    
    # Cek kata kunci masuk
    kata_masuk = ["gaji", "terima", "dapat", "masuk", "income", "pemasukan", "bonus", "freelance"]
    for kata in kata_masuk:
        if kata in text:
            tipe = "Masuk"
            break
    
    # Tentukan kategori
    if tipe == "Keluar":
        for kat, keywords in kategori_keluar.items():
            for kw in keywords:
                if kw in text:
                    kategori = kat.capitalize()
                    break
    else:
        for kat, keywords in kategori_masuk.items():
            for kw in keywords:
                if kw in text:
                    kategori = kat.capitalize()
                    break

    # Keterangan = teks tanpa angka
    keterangan = re.sub(r'\d+(?:\.\d+)?(?:k|rb|ribu|jt|juta)?', '', text).strip()
    keterangan = keterangan.replace("  ", " ").strip().title()
    if not keterangan:
        keterangan = "Transaksi"

    return {
        "keterangan": keterangan,
        "kategori": kategori,
        "jumlah": jumlah,
        "tipe": tipe
    }

# Format angka ke Rupiah
def rupiah(angka):
    return f"Rp {angka:,.0f}".replace(",", ".")

# Handler /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pesan = """👋 Halo! Aku bot keuangan pribadimu!

📝 *Cara pakai:*

*Catat pengeluaran:*
• `makan siang 25000`
• `bensin 50rb`
• `belanja shopee 150000`

*Catat pemasukan:*
• `gaji 5jt`
• `terima transfer 200000`

*Cek keuangan:*
• /rekap — ringkasan bulan ini
• /saldo — cek saldo sekarang
• /help — bantuan

Yuk mulai catat! 💪"""
    await update.message.reply_text(pesan, parse_mode="Markdown")

# Handler /help
async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pesan = """📖 *Panduan Lengkap*

*Format pengeluaran:*
`[keterangan] [jumlah]`
Contoh: `makan soto 15000`

*Format pemasukan:*
`gaji [jumlah]` atau `terima [jumlah]`
Contoh: `gaji 3jt`

*Satuan yang bisa dipakai:*
• `25000` atau `25rb` atau `25ribu` = Rp 25.000
• `5jt` atau `5juta` = Rp 5.000.000
• `50k` = Rp 50.000

*Perintah:*
• /rekap — rekap bulan ini
• /saldo — cek saldo
• /start — mulai ulang"""
    await update.message.reply_text(pesan, parse_mode="Markdown")

# Handler /saldo
async def saldo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        await update.message.reply_text("⏳ Mengambil data...")
        masuk, keluar, total_saldo, total_transaksi = hitung_total()
        emoji = "😊" if total_saldo >= 0 else "😰"
        pesan = f"""{emoji} *Saldo Kamu*

💚 Total Masuk: {rupiah(masuk)}
❤️ Total Keluar: {rupiah(keluar)}
💰 Saldo: {rupiah(total_saldo)}

📊 Total {total_transaksi} transaksi tercatat"""
        await update.message.reply_text(pesan, parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text("❌ Gagal ambil data. Coba lagi ya!")
        logger.error(e)

# Handler /rekap
async def rekap(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        await update.message.reply_text("⏳ Membuat rekap...")
        sheet = get_sheet()
        data = sheet.get_all_records()
        
        bulan_ini = datetime.now().strftime("%m/%Y")
        data_bulan = [row for row in data if str(row.get("Tanggal", "")).endswith(bulan_ini.split("/")[0] + "/" + bulan_ini.split("/")[1]) or bulan_ini.split("/")[0] in str(row.get("Tanggal", ""))]
        
        # Kalau filter bulan kosong, tampilkan semua
        if not data_bulan:
            data_bulan = data

        masuk = sum(row["Jumlah"] for row in data_bulan if row["Tipe"] == "Masuk")
        keluar = sum(row["Jumlah"] for row in data_bulan if row["Tipe"] == "Keluar")
        saldo_now = masuk - keluar

        # Rekap per kategori
        kategori_total = {}
        for row in data_bulan:
            if row["Tipe"] == "Keluar":
                kat = row.get("Kategori", "Lainnya")
                kategori_total[kat] = kategori_total.get(kat, 0) + row["Jumlah"]

        kat_text = ""
        for kat, total in sorted(kategori_total.items(), key=lambda x: x[1], reverse=True):
            kat_text += f"  • {kat}: {rupiah(total)}\n"

        bulan_nama = datetime.now().strftime("%B %Y")
        pesan = f"""📊 *Rekap {bulan_nama}*

💚 Pemasukan: {rupiah(masuk)}
❤️ Pengeluaran: {rupiah(keluar)}
💰 Saldo: {rupiah(saldo_now)}

📂 *Pengeluaran per Kategori:*
{kat_text if kat_text else "Belum ada data"}
📝 Total {len(data_bulan)} transaksi"""
        await update.message.reply_text(pesan, parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text("❌ Gagal buat rekap. Coba lagi ya!")
        logger.error(e)

# Handler pesan biasa
async def catat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    hasil = parse_pesan(text)
    
    if not hasil:
        await update.message.reply_text(
            "❓ Aku tidak mengerti pesanmu.\n\n"
            "Coba format: `makan siang 25000` atau `gaji 3jt`\n"
            "Ketik /help untuk panduan lengkap.",
            parse_mode="Markdown"
        )
        return
    
    try:
        tanggal = datetime.now().strftime("%d/%m/%Y")
        tambah_transaksi(
            tanggal,
            hasil["keterangan"],
            hasil["kategori"],
            hasil["jumlah"],
            hasil["tipe"]
        )
        
        emoji = "💚" if hasil["tipe"] == "Masuk" else "❤️"
        tipe_text = "Pemasukan" if hasil["tipe"] == "Masuk" else "Pengeluaran"
        
        pesan = f"""{emoji} *{tipe_text} tercatat!*

📝 {hasil["keterangan"]}
🏷️ Kategori: {hasil["kategori"]}
💵 {rupiah(hasil["jumlah"])}
📅 {tanggal}

Ketik /saldo untuk cek saldo kamu"""
        await update.message.reply_text(pesan, parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text("❌ Gagal menyimpan. Coba lagi ya!")
        logger.error(e)

# Main
def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("saldo", saldo))
    app.add_handler(CommandHandler("rekap", rekap))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, catat))
    logger.info("Bot started!")
    app.run_polling()

if __name__ == "__main__":
    main()
