from model import *
import hashlib
import difflib
from sentence_transformers import SentenceTransformer,util
import re
import requests

from pathlib import Path

model = SentenceTransformer("LazarusNLP/all-indo-e5-small-v4")

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
    url=f"https://vendorapi.lippomallpuri.com:8443/portal/api/tenant/v1/get?floorid=0&requeston={timestamp}"
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json().get("tenantDatas", [])
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

def jawab_pertanyaan(pertanyaan: str, corpus, metadata, model, threshold=0.35):
    pertanyaan = bersihkan_pertanyaan(pertanyaan)
    
    for alias, asli in brand_aliases.items():
        if alias in pertanyaan:
            pertanyaan = pertanyaan.replace(alias, asli)

    semua_nama = [d["TenantName"].lower() for d in metadata]
    cocok = difflib.get_close_matches(pertanyaan.lower(), semua_nama, n=1, cutoff=0.7)
    if cocok:
        nama_cocok = cocok[0]
        for d in metadata:
            if d["TenantName"].lower() == nama_cocok:
                lokasi = f"{d.get('Floor', '-')}, unit {d.get('Unit','')}".strip(", ")
                kategori = f"{d.get('SecondCategory','')} {d.get('MainCategory','')}".strip()
                deskripsi = d.get("Description", "")
                if deskripsi:
                    return f"{d['TenantName']} berada di lantai {lokasi} di Lippo Mall Puri, {deskripsi.strip()} (Kategori: {kategori})."
                return f"{d['TenantName']} berada di lantai {lokasi} di Lippo Mall Puri. Termasuk kategori {kategori}."
    
    query_embedding = model.encode(pertanyaan, convert_to_tensor=True)
    corpus_embeddings = model.encode(corpus, convert_to_tensor=True)
    scores = util.cos_sim(query_embedding, corpus_embeddings)[0]
    best_idx = scores.argmax().item()
    best_score = scores[best_idx]


    if best_score < threshold:
        return "Maaf, saya tidak menemukan jawaban yang cocok untuk pertanyaan Anda."

    if best_score < threshold:
        return "Maaf, saya tidak menemukan jawaban yang cocok untuk pertanyaan Anda."

    d = metadata[best_idx]
    lokasi = f"{d.get('Floor', '-')}, unit {d.get('Unit','')}".strip(", ")
    kategori = f"{d.get('SecondCategory','')} {d.get('MainCategory','')}".strip()
    deskripsi = d.get("Description", "")
    if deskripsi:
        return f"{d['TenantName']} berada di lantai {lokasi} di Lippo Mall Puri, {deskripsi.strip()} (Kategori: {kategori})."
    return f"{d['TenantName']} berada di lantai {lokasi} di Lippo Mall Puri. Termasuk kategori {kategori}."


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
