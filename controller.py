from model import *
import hashlib
import difflib
from sentence_transformers import SentenceTransformer,util
import re
import requests
from pathlib import Path
import urllib3
import torch

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# PERBAIKAN: Tambahkan device handling
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model = SentenceTransformer("LazarusNLP/all-indo-e5-small-v4")
model = model.to(device)

trigger_phrases = [
    "kalau", "jika", "gimana", "gimana kalau", "terus", "nah", "bagaimana dengan",
    "terus kalau", "terus gimana", "kalau saya mau", "kalau mau", "nah kalau"
]

def generate_signature(client_secret: str, timestamp: str):
    raw = f"{timestamp}{client_secret}"
    return hashlib.sha512(raw.encode("utf-8")).hexdigest().lower()

# Load tenant data from secured API
def load_tenant_data_from_api():
    
    client_key="NCeaWX3vyA"
    client_secret="cupAt9eJVRVsbOEbXJFTUuDhj6YUmw63"
    timestamp = datetime.now().strftime("%Y%m%d%H%M")
    headers = {
        "client-key": client_key,
        "signature-key": generate_signature(client_secret, timestamp)
    }
    print(headers)
    
    # url=f"https://vendorapi.lippomallpuri.com:8443/portal/api/tenant/v1/getsingle?tenantname=&requeston={timestamp}"
    url=f"https://vendorapi.lippomallpuri.com:8443/portal/api/tenant/v1/get?floorid=0&requeston={timestamp}"
    
    try:
        response = requests.get(url, headers=headers, verify=False)
        response.raise_for_status()
        data = response.json()
        
        print("Response data:", data)  # Debug: lihat struktur response
        
        # Handle berbagai format response
        if "tenantDatas" in data:
            tenant_list = data["tenantDatas"]
            print(f"Berhasil load {len(tenant_list)} tenant dari tenantDatas")
            return tenant_list
        elif "tenantData" in data:  # Untuk endpoint getsingle
            # Pastikan return dalam bentuk list
            if isinstance(data["tenantData"], dict):
                print("Berhasil load 1 tenant dari tenantData (dict)")
                return [data["tenantData"]]
            elif isinstance(data["tenantData"], list):
                print(f"Berhasil load {len(data['tenantData'])} tenant dari tenantData (list)")
                return data["tenantData"]
            else:
                print("Format tenantData tidak dikenali")
                return []
        else:
            print("Format response tidak dikenali:", data)
            return []
            
    except Exception as e:
        print("Gagal ambil tenant:", e)
        return []

def bersihkan_pertanyaan(pertanyaan):
    lower_q = pertanyaan.lower().strip()
    for phrase in sorted(trigger_phrases, key=len, reverse=True):
        pattern = r'^' + re.escape(phrase) + r'\s+'
        if re.match(pattern, lower_q):
            pertanyaan = re.sub(pattern, '', lower_q)
            break
    return pertanyaan.strip()

def load_tenant_data(filepath="newjson.json"):
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)["tenantDatas"]

def build_corpus(tenant_data, mall_name="Lippo Mall Puri"):
    corpus, metadata = [], []
    for item in tenant_data:
        brand = item.get("TenantName", "Nama tidak tersedia")
        floor = item.get("Floor", "lantai tidak diketahui")
        kategori = item.get("SecondCategory", "kategori tidak diketahui").replace("-", " ")
        grup = item.get("MainCategory", "kategori utama tidak diketahui")
        deskripsi = item.get("Description", "")

        if deskripsi:
            kalimat = f"{brand} adalah brand kategori {kategori} di {mall_name} lantai {floor} ada di {deskripsi}"
        else:
            kalimat = f"{brand} adalah brand kategori {kategori} yang berada di {mall_name} lantai {floor}, termasuk dalam grup {grup}."

        corpus.append(kalimat)
        metadata.append(item)
    return corpus, metadata

# tenant_data = load_tenant_data_from_api()
# corpus, metadata = build_corpus(tenant_data)

# ================
# Helper Functions
# ================
brand_aliases = {
    "kfc": "kentucky fried chicken",
    "xxi": "cinema xxi",
    "h&m": "h and m",
    "sfc": "seoul fried chicken"
}

def expand_query(pertanyaan):
    sinonim = {
        "baju": ["pakaian", "busana", "fashion"],
        "anak": ["bayi", "kids", "anak-anak"],
        "makanan": ["kuliner", "restoran", "makan", "food", "cafe"],
        "minuman": ["kopi", "beverage", "drink", "teh", "jus"],
        "kecantikan": ["kosmetik", "skincare", "beauty"],
        "sepatu": ["footwear", "shoes"],
        "elektronik": ["gadget", "smartphone", "laptop"],
        "olahraga": ["sport", "fitness"],
        "perhiasan": ["aksesoris", "emas", "jewelry"],
        "tas": ["bag", "backpack"],
        "mainan": ["toys", "boneka", "lego"]
    }

    for kata, daftar in sinonim.items():
        if kata in pertanyaan.lower():
            pertanyaan += " " + " ".join(daftar)
    return pertanyaan

# ============================================
# FUNGSI BARU: Deteksi Interaksi Sosial
# ============================================
def detect_social_interaction(pertanyaan, conversation_context=None):
    """Deteksi sapaan, ucapan terima kasih, dan interaksi sosial lainnya"""
    pertanyaan_lower = pertanyaan.lower().strip()
    
    # DETEKSI PENOLAKAN (tidak, tidak usah, tidak perlu)
    negative_words = [
        "tidak", "tidak usah", "tidak perlu", "gak", "gak usah", "gak perlu",
        "nggak", "nggak usah", "engga", "enggak", "ga", "ga usah", "ga perlu",
        "sudah", "sudah cukup", "cukup", "nanti saja", "skip"
    ]
    
    # Cek penolakan
    for neg in negative_words:
        if neg == pertanyaan_lower or pertanyaan_lower.startswith(neg + " "):
            return "negative", "Baik, tidak masalah! Senang bisa membantu. 😊"
    
    # PERBAIKAN: Cek dulu apakah ini permintaan rekomendasi lagi (PRIORITAS TERTINGGI)
    if conversation_context and "last_category" in conversation_context:
        # Kata-kata afirmatif yang menunjukkan user setuju/ingin lanjut
        affirmative_words = [
            "iya", "ya", "yap", "yup", "yoi", "yep", "yeah", "yes",
            "boleh", "oke", "ok", "okay", "okey", "sip", "siap",
            "mau", "pengen", "ingin"
        ]
        
        more_words = [
            "lagi", "lainnya", "yang lain", "ada lagi", "masih ada",
            "selain itu", "opsi lain", "pilihan lain", "rekomendasi lain"
        ]
        
        # Split pertanyaan jadi kata-kata
        words = pertanyaan_lower.split()
        
        # Cek jika pertanyaan sangat singkat (1-3 kata) dan mengandung kata afirmatif
        if len(words) <= 3:
            for word in affirmative_words:
                if word == pertanyaan_lower or word in words:
                    return "more", None
        
        # Atau cek jika ada kata "lagi" / variasinya (bahkan untuk pertanyaan lebih panjang)
        for word in more_words:
            if word in pertanyaan_lower:
                return "more", None
    
    # Sapaan
    greetings = {
        "halo": "Halo! Selamat datang di Lippo Mall Puri. Ada yang bisa saya bantu?",
        "hai": "Hai! Ada yang bisa saya bantu hari ini?",
        "hi": "Hi! Selamat datang. Ada yang ingin Anda tanyakan?",
        "selamat pagi": "Selamat pagi! Semoga hari Anda menyenangkan. Ada yang bisa saya bantu?",
        "selamat siang": "Selamat siang! Ada yang bisa saya bantu?",
        "selamat sore": "Selamat sore! Ada yang bisa saya bantu hari ini?",
        "selamat malam": "Selamat malam! Ada yang bisa saya bantu?",
        "pagi": "Selamat pagi! Ada yang bisa saya bantu?",
        "siang": "Selamat siang! Ada yang ingin Anda tanyakan?",
        "sore": "Selamat sore! Ada yang bisa saya bantu?",
        "malam": "Selamat malam! Bagaimana saya bisa membantu Anda?"
    }
    
    # Ucapan terima kasih
    thanks = [
        "terima kasih", "terimakasih", "thanks", "thank you", "makasih", 
        "thx", "tq", "tengkyu", "thanks ya", "terima kasih ya"
    ]
    
    # Ucapan selamat tinggal
    goodbyes = [
        "bye", "dadah", "selamat tinggal", "sampai jumpa", "jumpa lagi",
        "see you", "goodbye", "dah"
    ]
    
    # Cek sapaan
    for greeting, response_text in greetings.items():
        if pertanyaan_lower == greeting or pertanyaan_lower.startswith(greeting + " "):
            return "greeting", response_text
    
    # Cek ucapan terima kasih
    for thank in thanks:
        if thank in pertanyaan_lower:
            return "thanks", "Sama-sama! Senang bisa membantu. 😊"
    
    # Cek ucapan selamat tinggal
    for goodbye in goodbyes:
        if goodbye in pertanyaan_lower:
            return "goodbye", "Terima kasih sudah berkunjung! Sampai jumpa lagi di Lippo Mall Puri! 👋"
    
    return None, None

# ============================================
# FUNGSI BARU: Deteksi query kategori (DIPERBAIKI)
# ============================================
def detect_category_query(pertanyaan):
    """Deteksi apakah pertanyaan menanyakan kategori/rekomendasi tenant"""
    category_keywords = {
        # Makanan & Minuman (dengan filter lebih ketat)
        "makanan": {
            "categories": ["Restaurant", "Food", "Fast Food"],
            "exclude": ["Bakery", "Cake", "Pastry"]  # Exclude toko kue/roti
        },
        "makan": {
            "categories": ["Restaurant", "Food", "Fast Food"],
            "exclude": ["Bakery", "Cake", "Pastry"]
        },
        "restoran": {
            "categories": ["Restaurant", "Food"],
            "exclude": ["Bakery", "Cake", "Pastry"]
        },
        "kuliner": {
            "categories": ["Restaurant", "Food", "Culinary"],
            "exclude": ["Bakery", "Cake", "Pastry"]
        },
        "kopi": {
            "categories": ["Coffee", "Cafe"],
            "exclude": []
        },
        "cafe": {
            "categories": ["Cafe", "Coffee"],
            "exclude": []
        },
        
        # Fashion & Apparel
        "baju": {
            "categories": ["Fashion", "Apparel", "Clothing"],
            "exclude": ["Shoes", "Bag", "Accessories"]
        },
        "pakaian": {
            "categories": ["Fashion", "Apparel", "Clothing"],
            "exclude": ["Shoes", "Bag", "Accessories"]
        },
        "fashion": {
            "categories": ["Fashion", "Apparel"],
            "exclude": ["Shoes", "Bag"]
        },
        "celana": {
            "categories": ["Fashion", "Apparel", "Clothing"],
            "exclude": ["Shoes", "Bag", "Accessories"]
        },
        "kaos": {
            "categories": ["Fashion", "Apparel", "Clothing"],
            "exclude": ["Shoes", "Bag", "Accessories"]
        },
        
        # Sepatu & Tas
        "sepatu": {
            "categories": ["Shoes", "Footwear"],
            "exclude": []
        },
        "sandal": {
            "categories": ["Shoes", "Footwear"],
            "exclude": []
        },
        "tas": {
            "categories": ["Bag", "Fashion"],
            "exclude": []
        },
        "ransel": {
            "categories": ["Bag"],
            "exclude": []
        },
        "backpack": {
            "categories": ["Bag"],
            "exclude": []
        },
        
        # Elektronik & Gadget
        "elektronik": {
            "categories": ["Electronics", "Gadget", "Computer", "Technology"],
            "exclude": []
        },
        "gadget": {
            "categories": ["Electronics", "Gadget", "Technology"],
            "exclude": []
        },
        "handphone": {
            "categories": ["Electronics", "Gadget", "Phone", "Mobile"],
            "exclude": []
        },
        "hp": {
            "categories": ["Electronics", "Gadget", "Phone", "Mobile"],
            "exclude": []
        },
        "laptop": {
            "categories": ["Electronics", "Computer", "Technology"],
            "exclude": []
        },
        "komputer": {
            "categories": ["Electronics", "Computer", "Technology"],
            "exclude": []
        },
        
        # Kecantikan
        "kecantikan": {
            "categories": ["Beauty", "Cosmetics", "Skincare", "Pharmacies"],
            "exclude": []
        },
        "kosmetik": {
            "categories": ["Beauty", "Cosmetics"],
            "exclude": []
        },
        "skincare": {
            "categories": ["Beauty", "Skincare"],
            "exclude": []
        },
        "makeup": {
            "categories": ["Beauty", "Cosmetics"],
            "exclude": []
        },
        
        # Lainnya
        "mainan": {
            "categories": ["Toys", "Kids"],
            "exclude": []
        },
        "olahraga": {
            "categories": ["Sport", "Fitness"],
            "exclude": []
        },
        "sport": {
            "categories": ["Sport", "Fitness"],
            "exclude": []
        },
        "fitness": {
            "categories": ["Fitness", "Sport", "Gym"],
            "exclude": []
        },
        "gym": {
            "categories": ["Fitness", "Sport", "Gym"],
            "exclude": []
        },
        "perhiasan": {
            "categories": ["Jewelry", "Accessories"],
            "exclude": []
        },
        "emas": {
            "categories": ["Jewelry", "Gold"],
            "exclude": []
        },
        "aksesoris": {
            "categories": ["Accessories", "Fashion"],
            "exclude": []
        },
        
        # Fast Food Specific
        "burger": {
            "categories": ["Fast Food", "Restaurant"],
            "exclude": ["Bakery", "Cafe"]
        },
        "pizza": {
            "categories": ["Restaurant", "Fast Food"],
            "exclude": ["Bakery"]
        },
        "ayam": {
            "categories": ["Fast Food", "Restaurant"],
            "exclude": ["Bakery"]
        },
        "nasi": {
            "categories": ["Restaurant", "Food"],
            "exclude": ["Bakery"]
        },
        "sushi": {
            "categories": ["Restaurant", "Japanese"],
            "exclude": []
        },
        "ramen": {
            "categories": ["Restaurant", "Japanese"],
            "exclude": []
        },
        "bakso": {
            "categories": ["Restaurant", "Indonesian"],
            "exclude": []
        },
        "soto": {
            "categories": ["Restaurant", "Indonesian"],
            "exclude": []
        }
    }
    
    pertanyaan_lower = pertanyaan.lower()
    
    # Cek apakah ada trigger words untuk rekomendasi
    trigger_words = ["tempat", "rekomendasi", "ada", "dimana", "cari", "mau", "pengen", "mana", "yang", "jual", "toko", "beli", "membeli", "shop"]
    has_trigger = any(word in pertanyaan_lower for word in trigger_words)
    
    if has_trigger:
        for keyword, config in category_keywords.items():
            if keyword in pertanyaan_lower:
                return config["categories"], config["exclude"], keyword
    
    return None, None, None

# ============================================
# FUNGSI BARU: Ambil multiple tenant by category (DIPERBAIKI)
# ============================================
def get_tenants_by_categories(categories, metadata, exclude_categories=None, max_results=5, offset=0):
    """Ambil tenant berdasarkan kategori dengan filter exclude"""
    results = []
    seen_names = set()
    
    if exclude_categories is None:
        exclude_categories = []
    
    for item in metadata:
        second_cat = item.get("SecondCategory", "").lower()
        main_cat = item.get("MainCategory", "").lower()
        tenant_name = item.get("TenantName", "")
        
        # Skip jika sudah ada
        if tenant_name in seen_names:
            continue
        
        # FILTER: Skip jika masuk kategori exclude
        is_excluded = False
        for exclude_cat in exclude_categories:
            if exclude_cat.lower() in second_cat or exclude_cat.lower() in main_cat:
                is_excluded = True
                break
        
        if is_excluded:
            continue
        
        # Cek apakah kategori cocok
        for cat in categories:
            cat_lower = cat.lower()
            if cat_lower in second_cat or cat_lower in main_cat:
                floor = item.get("Floor", "")
                unit = item.get("Unit", "")
                
                results.append({
                    "name": tenant_name,
                    "floor": floor,
                    "unit": unit,
                    "category": item.get("SecondCategory", "")
                })
                seen_names.add(tenant_name)
                break
    
    # Return hasil dengan offset
    return results[offset:offset + max_results], len(results)

# ============================================
# FUNGSI: Find Neighbor Tenants
# ============================================
def extract_unit_number(unit_str):
    """Ekstrak nomor dari unit string"""
    if not unit_str:
        return None
    matches = re.findall(r'(\d+)', unit_str)
    if matches:
        return int(matches[-1])
    return None

def get_prefix_suffix(unit_str):
    """Ekstrak prefix dan suffix dari unit"""
    if not unit_str:
        return None, None
    match = re.match(r'^([A-Z]+[\-]?)(\d+)([A-Z]?)$', unit_str.strip())
    if match:
        return match.group(1), match.group(3)
    
    match = re.match(r'^(\d+[\-])(\d+)([A-Z]?)$', unit_str.strip())
    if match:
        return match.group(1), match.group(3)
    
    return None, None

def find_neighbor_tenants(current_tenant, metadata):
    """Cari 2 tenant terdekat berdasarkan nomor unit"""
    unit = current_tenant.get("Unit", "")
    floor = current_tenant.get("Floor", "")
    
    unit_num = extract_unit_number(unit)
    if unit_num is None:
        return []
    
    prefix, suffix = get_prefix_suffix(unit)
    if prefix is None:
        return []
    
    candidates = []
    for tenant in metadata:
        tenant_unit = tenant.get("Unit", "")
        tenant_floor = tenant.get("Floor", "")
        tenant_num = extract_unit_number(tenant_unit)
        tenant_prefix, tenant_suffix = get_prefix_suffix(tenant_unit)
        
        if tenant.get("TenantName") == current_tenant.get("TenantName"):
            continue
        
        if tenant_floor == floor and tenant_prefix == prefix and tenant_num is not None:
            distance = abs(tenant_num - unit_num)
            candidates.append({
                "name": tenant.get("TenantName"),
                "unit": tenant_unit,
                "distance": distance,
                "unit_num": tenant_num
            })
    
    candidates.sort(key=lambda x: x['distance'])
    neighbors = candidates[:2]
    
    return neighbors

# ============================================
# FUNGSI UTAMA: Jawab Pertanyaan (DIPERBAIKI)
# ============================================
def jawab_pertanyaan(pertanyaan: str, corpus, metadata, model, threshold=0.35, conversation_context=None):
    """
    Main function untuk menjawab pertanyaan dengan kemampuan interaktif
    
    Args:
        pertanyaan: Pertanyaan dari user
        corpus: Corpus data tenant
        metadata: Metadata tenant
        model: Sentence transformer model
        threshold: Threshold untuk similarity
        conversation_context: Dictionary untuk menyimpan context percakapan (optional)
    """
    # Validasi corpus tidak kosong
    if not corpus or len(corpus) == 0:
        return "Maaf, data tenant tidak tersedia saat ini."
    
    if not metadata or len(metadata) == 0:
        return "Maaf, data tenant tidak tersedia saat ini."
    
    # PRIORITAS 0: Deteksi interaksi sosial (PASS conversation_context!)
    interaction_type, response = detect_social_interaction(pertanyaan, conversation_context)
    
    if interaction_type == "greeting":
        return response
    
    if interaction_type == "thanks":
        return response
    
    if interaction_type == "goodbye":
        return response
    
    if interaction_type == "negative":
        return response
    
    # PERBAIKAN: Handle permintaan rekomendasi lagi
    if interaction_type == "more":
        # Jika user minta rekomendasi lagi, cek context
        if conversation_context and "last_category" in conversation_context:
            categories = conversation_context["last_category"]
            exclude_cats = conversation_context.get("last_exclude", [])
            keyword = conversation_context["last_keyword"]
            offset = conversation_context.get("offset", 0) + 5
            
            tenants, total = get_tenants_by_categories(categories, metadata, exclude_cats, max_results=5, offset=offset)
            
            if tenants:
                # Update context
                conversation_context["offset"] = offset
                
                # Format jawaban
                intro = f"Berikut rekomendasi {keyword} lainnya di Lippo Mall Puri:\n\n"
                tenant_list = []
                for i, t in enumerate(tenants, 1):
                    tenant_list.append(f"  {i}. {t['name']}\n     📍 Lantai {t['floor']}, Unit {t['unit']}")
                
                response = intro + "\n\n".join(tenant_list)
                
                return response
            else:
                return "Maaf, tidak ada rekomendasi lainnya saat ini."
        else:
            # Jika tidak ada context, minta klarifikasi
            return "Maaf, saya tidak yakin rekomendasi apa yang Anda maksud. Bisa tolong sebutkan kategori yang Anda cari?"
    
    pertanyaan_cleaned = bersihkan_pertanyaan(pertanyaan)
    
    for alias, asli in brand_aliases.items():
        if alias in pertanyaan_cleaned:
            pertanyaan_cleaned = pertanyaan_cleaned.replace(alias, asli)

    # PERBAIKAN PRIORITAS 1: Cek kecocokan langsung berdasarkan nama tenant DULU
    # Ini penting agar "kopi kenangan" dicari sebagai nama tenant, bukan kategori kopi
    semua_nama = [d["TenantName"].lower() for d in metadata]
    cocok = difflib.get_close_matches(pertanyaan_cleaned.lower(), semua_nama, n=1, cutoff=0.6)
    
    if cocok:
        nama_cocok = cocok[0]
        for d in metadata:
            if d["TenantName"].lower() == nama_cocok:
                floor = d.get('Floor', '')
                unit = d.get('Unit', '')
                description = d.get('Description', '')
                
                # Build lokasi string
                lokasi = f"{floor}"
                if unit:
                    lokasi += f", unit {unit}"
                
                # Build response: URUTAN - di dekat dulu, Lippo Mall Puri terakhir
                response = f"{d['TenantName']} berada di lantai {lokasi}"
                
                # Tambahkan description jika ada
                if description and description.strip():
                    response += f", {description.strip()}"
                
                # Tambah neighbor (DI DEKAT DULU)
                neighbors = find_neighbor_tenants(d, metadata)
                if len(neighbors) == 2:
                    response += f", di dekat {neighbors[0]['name']} dan {neighbors[1]['name']}"
                elif len(neighbors) == 1:
                    response += f", di dekat {neighbors[0]['name']}"
                
                # LIPPO MALL PURI TERAKHIR
                response += " di Lippo Mall Puri."
                
                return response
    
    # ============================================
    # PRIORITAS 2: Cek apakah ini query kategori/rekomendasi
    # PERBAIKAN: Hanya jalankan jika bukan nama tenant
    # ============================================
    categories, exclude_cats, keyword = detect_category_query(pertanyaan)
    
    if categories:
        # Ambil tenant berdasarkan kategori dengan exclude filter
        tenants, total = get_tenants_by_categories(categories, metadata, exclude_cats, max_results=5, offset=0)
        
        if tenants:
            # Simpan context untuk follow-up
            if conversation_context is not None:
                conversation_context["last_category"] = categories
                conversation_context["last_exclude"] = exclude_cats
                conversation_context["last_keyword"] = keyword
                conversation_context["offset"] = 0
            
            # Format jawaban dengan list tenant
            intro = f"Berikut ini beberapa rekomendasi {keyword} di Lippo Mall Puri:\n\n"
            tenant_list = []
            for i, t in enumerate(tenants, 1):
                tenant_list.append(f"  {i}. {t['name']}\n     📍 Lantai {t['floor']}, Unit {t['unit']}")
            
            response = intro + "\n\n".join(tenant_list)
            
            return response
        else:
            return f"Maaf, saya tidak menemukan tenant {keyword} di Lippo Mall Puri."
    
    # PRIORITAS 3: Embedding similarity
    # PERBAIKAN: Pastikan semua tensor di device yang sama
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    
    # Pastikan model ada di device yang benar
    model = model.to(device)
    
    query_embedding = model.encode(pertanyaan_cleaned, convert_to_tensor=True, device=device)
    corpus_embeddings = model.encode(corpus, convert_to_tensor=True, device=device)
    
    # Pastikan kedua embedding di device yang sama sebelum cos_sim
    query_embedding = query_embedding.to(device)
    corpus_embeddings = corpus_embeddings.to(device)
    
    scores = util.cos_sim(query_embedding, corpus_embeddings)[0]
    best_idx = scores.argmax().item()
    best_score = scores[best_idx]


    if best_score < threshold:
        return "Maaf, saya tidak menemukan jawaban yang cocok untuk pertanyaan Anda. Bisa tolong diulang atau dijelaskan dengan cara lain?"

    d = metadata[best_idx]
    floor = d.get('Floor', '')
    unit = d.get('Unit', '')
    description = d.get('Description', '')
    
    # Build lokasi string
    lokasi = f"{floor}"
    if unit:
        lokasi += f", unit {unit}"
    
    # Build response: URUTAN - di dekat dulu, Lippo Mall Puri terakhir
    response = f"{d['TenantName']} berada di lantai {lokasi}"
    
    # Tambahkan description jika ada
    if description and description.strip():
        response += f", {description.strip()}"
    
    # Tambah neighbor (DI DEKAT DULU)
    neighbors = find_neighbor_tenants(d, metadata)
    if len(neighbors) == 2:
        response += f", di dekat {neighbors[0]['name']} dan {neighbors[1]['name']}"
    elif len(neighbors) == 1:
        response += f", di dekat {neighbors[0]['name']}"
    
    # LIPPO MALL PURI TERAKHIR
    response += " di Lippo Mall Puri."
    
    return response


# with open("tenant_qa.json", "r", encoding="utf-8") as f:
#     qa_data = json.load(f)
# all_questions = [item["question"] for item in qa_data]

def is_valid_signature_v2(client_key: str, signature_key: str, requesttimestamp: str) -> bool:
    try:
        # Pastikan client dikenal        
        signature_key_db = get_user_key(client_key)
        if signature_key_db == False:
            return False

        # Validasi timestamp tidak lebih dari 5 menit
        ts = datetime.strptime(requesttimestamp, "%Y%m%d%H%M")
        print(ts)
        now = datetime.now()
        if abs((now - ts).total_seconds()) > 300:
            print("⏱️ requesttimestamp terlalu lama atau belum waktunya")
            return False
        
        # Hitung SHA512(timestamp + clientsecret)
        raw = f"{requesttimestamp}{signature_key_db}".encode("utf-8")
        print(raw)
        expected_signature = hashlib.sha512(raw).hexdigest().lower()
        print(expected_signature)
        print(signature_key)
        if expected_signature == signature_key.lower():
            print("cocok")
            return True
        else:
            print("❌ Signature tidak cocok")
            return False

    except Exception as e:
        print(f"❌ Error validasi signature: {e}")
        return False

# def find_best_answer(user_question):
#     match = difflib.get_close_matches(user_question, all_questions, n=1, cutoff=0.5)
#     if match:
#         for item in qa_data:
#             if item["question"] == match[0]:
#                 return item["answer"]
#     return "Maaf, saya tidak menemukan jawaban yang cocok."