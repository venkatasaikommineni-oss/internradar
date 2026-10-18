"""Curated Indian city and state list. Comprehensive coverage across India."""
import re

CITIES = [
    # ── Major metros ──────────────────────────────────────────────────────
    "Bengaluru", "Mumbai", "Delhi", "Hyderabad", "Chennai", "Kolkata", "Pune", "Ahmedabad",
    # ── NCR ───────────────────────────────────────────────────────────────
    "Gurugram", "Noida", "Ghaziabad", "Faridabad", "Greater Noida",
    # ── UP ────────────────────────────────────────────────────────────────
    "Lucknow", "Kanpur", "Varanasi", "Prayagraj", "Agra", "Meerut", "Bareilly", "Aligarh",
    "Moradabad", "Gorakhpur", "Mathura", "Firozabad", "Saharanpur", "Rampur", "Shahjahanpur",
    "Sambhal", "Hapur", "Muzaffarnagar", "Lakhimpur Kheri", "Sitapur", "Hardoi",
    "Jhansi", "Banda", "Chitrakoot", "Hamirpur", "Mahoba", "Unnao", "Rae Bareli",
    "Sultanpur", "Faizabad", "Ayodhya", "Ambedkar Nagar", "Basti", "Gonda",
    "Balrampur", "Shravasti", "Bahraich", "Sravasti", "Azamgarh", "Mau",
    # ── Rajasthan ─────────────────────────────────────────────────────────
    "Jaipur", "Jodhpur", "Udaipur", "Kota", "Bikaner", "Ajmer", "Bhilwara", "Alwar",
    "Bharatpur", "Sikar", "Pali", "Sriganganagar", "Barmer", "Jhalawar", "Tonk",
    "Baran", "Bundi", "Churu", "Jhunjhunu", "Nagaur", "Dholpur", "Karauli",
    # ── Gujarat ───────────────────────────────────────────────────────────
    "Surat", "Vadodara", "Rajkot", "Gandhinagar", "Bhavnagar", "Jamnagar", "Vapi",
    "Anand", "Nadiad", "Mehsana", "Morbi", "Surendranagar", "Botad", "Amreli",
    "Junagadh", "Porbandar", "Gir Somnath", "Dwarka", "Kutch", "Bhuj", "Gandhidham",
    "Palanpur", "Patan", "Banaskantha", "Dahod", "Godhra", "Navsari", "Valsad",
    # ── Maharashtra ───────────────────────────────────────────────────────
    "Nashik", "Aurangabad", "Thane", "Navi Mumbai", "Goa", "Nagpur", "Kolhapur",
    "Solapur", "Sangli", "Akola", "Amravati", "Latur", "Nanded", "Jalgaon",
    "Dhule", "Ahmednagar", "Chandrapur", "Beed", "Osmanabad", "Yavatmal",
    "Buldhana", "Washim", "Hingoli", "Parbhani", "Raigad", "Ratnagiri", "Sindhudurg",
    "Wardha", "Gondiya", "Bhandara", "Gadchiroli", "Satara", "Sholapur",
    # ── Karnataka ─────────────────────────────────────────────────────────
    "Mysuru", "Mangaluru", "Hubballi", "Belagavi", "Tumakuru", "Kalaburagi",
    "Davangere", "Ballari", "Vijayapura", "Bidar", "Raichur", "Koppal", "Gadag",
    "Haveri", "Dharwad", "Uttara Kannada", "Kodagu", "Hassan", "Shivamogga",
    "Chikkamagaluru", "Chitradurga", "Davanagere", "Mandya", "Chamrajnagar", "Yadgir",
    "Udupi", "Manipal",
    # ── Andhra Pradesh ────────────────────────────────────────────────────
    "Visakhapatnam", "Vijayawada", "Guntur", "Amaravati", "Tirupati", "Nellore",
    "Kurnool", "Kakinada", "Rajahmundry", "Eluru", "Anantapur", "Kadapa", "Chittoor",
    "Srikakulam", "Vizianagaram", "Ongole", "Proddatur", "Machilipatnam", "Nandyal",
    "Hindupur", "Bhimavaram", "Narasaraopet", "Tenali",
    # ── Telangana ─────────────────────────────────────────────────────────
    "Warangal", "Karimnagar", "Nizamabad", "Khammam", "Nalgonda", "Adilabad",
    "Mancherial", "Suryapet", "Siddipet", "Jagtial", "Sangareddy", "Yadadri",
    "Mahabubnagar", "Medak", "Bhadradri Kothagudem", "Kumuram Bheem",
    # ── Tamil Nadu ────────────────────────────────────────────────────────
    "Coimbatore", "Madurai", "Tiruchirappalli", "Vellore", "Erode", "Tiruppur",
    "Thanjavur", "Salem", "Tirunelveli", "Dindigul", "Kancheepuram", "Nagercoil",
    "Cuddalore", "Sivakasi", "Karur", "Udhagamandalam", "Ooty", "Kumbakonam",
    "Namakkal", "Pudukkottai", "Ariyalur", "Perambalur", "Villupuram",
    "Kallakurichi", "Ranipet", "Tenkasi", "Tirupattur", "Chengalpattu",
    # ── Kerala ────────────────────────────────────────────────────────────
    "Kochi", "Thiruvananthapuram", "Kozhikode", "Kollam", "Thrissur", "Palakkad",
    "Malappuram", "Kannur", "Kasaragod", "Kottayam", "Alappuzha", "Ernakulam",
    "Idukki", "Pathanamthitta", "Wayanad",
    # ── West Bengal ───────────────────────────────────────────────────────
    "Howrah", "Durgapur", "Asansol", "Siliguri", "Bardhaman", "Malda", "Murshidabad",
    "Krishnanagar", "Haldia", "Kharagpur", "Midnapore", "Bankura", "Purulia",
    "Birbhum", "Cooch Behar", "Jalpaiguri", "Darjeeling", "Nadia",
    # ── Odisha ────────────────────────────────────────────────────────────
    "Bhubaneswar", "Cuttack", "Rourkela", "Berhampur", "Sambalpur", "Balasore",
    "Baripada", "Bhadrak", "Jharsuguda", "Kendujhar", "Puri", "Paradip",
    # ── Bihar ─────────────────────────────────────────────────────────────
    "Patna", "Gaya", "Muzaffarpur", "Bhagalpur", "Darbhanga", "Purnia", "Arrah",
    "Bihar Sharif", "Begusarai", "Katihar", "Saharsa", "Munger", "Buxar",
    "Sitamarhi", "Hajipur", "Chapra", "Nalanda", "Vaishali",
    # ── Jharkhand ─────────────────────────────────────────────────────────
    "Ranchi", "Jamshedpur", "Dhanbad", "Bokaro", "Hazaribagh", "Deoghar",
    "Giridih", "Dumka", "Ramgarh", "Chaibasa",
    # ── Madhya Pradesh ────────────────────────────────────────────────────
    "Indore", "Bhopal", "Jabalpur", "Gwalior", "Ujjain", "Sagar", "Rewa",
    "Satna", "Dewas", "Chhindwara", "Ratlam", "Vidisha", "Damoh", "Mandsaur",
    "Neemuch", "Morena", "Bhind", "Shivpuri", "Guna", "Katni", "Hoshangabad",
    "Balaghat", "Seoni", "Narsinghpur",
    # ── Chhattisgarh ──────────────────────────────────────────────────────
    "Raipur", "Bhilai", "Durg", "Bilaspur", "Korba", "Raigarh", "Jagdalpur",
    "Rajnandgaon", "Ambikapur",
    # ── Himachal Pradesh ──────────────────────────────────────────────────
    "Shimla", "Dharamsala", "Mandi", "Solan", "Nahan", "Hamirpur", "Kullu",
    "Baddi", "Palampur",
    # ── Uttarakhand ───────────────────────────────────────────────────────
    "Dehradun", "Haridwar", "Roorkee", "Rishikesh", "Nainital", "Almora", "Haldwani",
    "Rudrapur", "Kashipur", "Kotdwar",
    # ── Punjab ────────────────────────────────────────────────────────────
    "Chandigarh", "Mohali", "Amritsar", "Ludhiana", "Jalandhar", "Patiala",
    "Bathinda", "Pathankot", "Hoshiarpur", "Gurdaspur", "Firozpur", "Sangrur",
    "Moga", "Muktsar", "Fazilka",
    # ── Haryana ───────────────────────────────────────────────────────────
    "Panipat", "Sonipat", "Karnal", "Ambala", "Hisar", "Rohtak", "Yamunanagar",
    "Bhiwani", "Palwal", "Sirsa", "Fatehabad", "Mewat", "Nuh", "Jhajjar",
    "Rewari", "Mahendragarh",
    # ── J&K / Ladakh ──────────────────────────────────────────────────────
    "Srinagar", "Jammu", "Leh", "Kargil", "Anantnag", "Baramulla", "Kathua",
    # ── Northeast ─────────────────────────────────────────────────────────
    "Guwahati", "Dibrugarh", "Silchar", "Jorhat", "Nagaon", "Sivasagar",
    "Shillong", "Imphal", "Agartala", "Aizawl", "Kohima", "Dimapur",
    "Gangtok", "Itanagar", "Tezpur", "Diphu",
    # ── Puducherry, Goa, A&N ──────────────────────────────────────────────
    "Puducherry", "Panaji", "Margao", "Vasco da Gama", "Port Blair",
    # ── Telangana / Andhra additions ──────────────────────────────────────
    "Secunderabad", "Kompally", "LB Nagar", "Kukatpally", "Madhapur",
    # ── IT hubs / tech parks ──────────────────────────────────────────────
    "Electronic City", "Whitefield", "Koramangala", "Indiranagar",
    "Banjara Hills", "Hitech City", "Gachibowli", "Cyber City",
    "Salt Lake", "Rajarhat", "New Town",
]
CITIES = sorted(set(CITIES))

ALIASES = {
    "bangalore": "Bengaluru",
    "bengaluru": "Bengaluru",
    "bombay": "Mumbai",
    "madras": "Chennai",
    "calcutta": "Kolkata",
    "new delhi": "Delhi",
    "delhi ncr": "Delhi",
    "ncr": "Delhi",
    "gurgaon": "Gurugram",
    "mysore": "Mysuru",
    "mangalore": "Mangaluru",
    "cochin": "Kochi",
    "trivandrum": "Thiruvananthapuram",
    "vizag": "Visakhapatnam",
    "allahabad": "Prayagraj",
    "baroda": "Vadodara",
    "trichy": "Tiruchirappalli",
    "pondicherry": "Puducherry",
    "hyd": "Hyderabad",
    "secunderabad": "Hyderabad",
    "calicut": "Kozhikode",
    "udupi": "Manipal",
    "nashik": "Nashik",
    "aurangabad": "Aurangabad",
    "tirupur": "Tiruppur",
    "cbe": "Coimbatore",
    "blr": "Bengaluru",
    "mum": "Mumbai",
    "pune": "Pune",
    "kolkata": "Kolkata",
    "chennai": "Chennai",
    "delhi": "Delhi",
    "hyderabad": "Hyderabad",
    "ahmedabad": "Ahmedabad",
    "noida": "Noida",
    "goa": "Panaji",
    "ooty": "Udhagamandalam",
}
for _c in CITIES:
    ALIASES.setdefault(_c.lower(), _c)

_CITY_RE = re.compile(
    r"(?<![a-z])({"
    .replace("{", "")
    + "|".join(re.escape(a) for a in sorted(ALIASES, key=len, reverse=True))
    + r")(?![a-z])"
)


def normalize_city(text: str | None) -> str | None:
    """Return canonical city name found inside free text, else None."""
    if not text:
        return None
    m = _CITY_RE.search(text.lower())
    return ALIASES[m.group(1)] if m else None


def canonical_city_exact(text: str | None) -> str | None:
    """Strict lookup for user-submitted values: must be a known city/alias."""
    if not text:
        return None
    return ALIASES.get(text.strip().lower())


def is_india(location: str | None) -> bool:
    if not location:
        return False
    low = location.lower()
    return "india" in low or normalize_city(low) is not None


_STATES = (
    "andhra pradesh|arunachal pradesh|assam|bihar|chhattisgarh|goa|gujarat|haryana|himachal pradesh|"
    "jharkhand|karnataka|kerala|madhya pradesh|maharashtra|manipur|meghalaya|mizoram|nagaland|odisha|"
    "orissa|punjab|rajasthan|sikkim|tamil nadu|telangana|tripura|uttar pradesh|uttarakhand|west bengal|"
    "jammu and kashmir|ladakh|chandigarh|puducherry|andaman|lakshadweep|dadra|daman|diu"
)
_STATE_RE = re.compile(r"(?<![a-z])(" + _STATES + r")(?![a-z])")
_REMOTE_RE = re.compile(r"\bremote\b|work from home|\bwfh\b|anywhere|worldwide|\bglobal\b|\bapac\b|\basia\b")
_VAGUE_RE = re.compile(r"\b(multiple|various|several|flexible|pan.?india|all.?india)\b")
_FOREIGN_RE = re.compile(
    r"\b(usa|us|united states|america|uk|united kingdom|england|britain|canada|europe|emea|eu|germany|"
    r"france|spain|italy|poland|netherlands|ireland|portugal|sweden|switzerland|australia|new zealand|"
    r"singapore|japan|china|korea|brazil|mexico|latam|north america|south america|uae|dubai|israel|"
    r"nigeria|kenya|south africa|philippines|indonesia|malaysia|vietnam|thailand)\b"
)


def in_india_scope(location: str | None) -> bool:
    """India-first filter. unknown/vague -> kept. India city/state/remote -> kept."""
    if not location or not location.strip():
        return True
    low = location.lower()
    if "india" in low or normalize_city(low) or _STATE_RE.search(low):
        return True
    if _REMOTE_RE.search(low):
        return not _FOREIGN_RE.search(low)
    return bool(_VAGUE_RE.search(low))


def suggest_cities(q: str, limit: int = 15) -> list[str]:
    q = (q or "").strip().lower()
    if not q:
        return CITIES[:limit]
    starts = [c for c in CITIES if c.lower().startswith(q)]
    contains = [c for c in CITIES if q in c.lower() and c not in starts]
    alias_hits = [ALIASES[a] for a in ALIASES if a.startswith(q) and ALIASES[a] not in starts]
    out: list[str] = []
    for c in starts + alias_hits + contains:
        if c not in out:
            out.append(c)
    return out[:limit]


# Cities that share one commuting / hiring region
_REGIONS = [
    {"Delhi", "Gurugram", "Noida", "Ghaziabad", "Faridabad", "Greater Noida"},
    {"Mumbai", "Navi Mumbai", "Thane"},
    {"Chandigarh", "Mohali", "Panchkula"},
    {"Vijayawada", "Guntur", "Amaravati"},
    {"Bengaluru", "Mysuru", "Electronic City", "Whitefield", "Koramangala"},
    {"Hyderabad", "Secunderabad", "Hitech City", "Gachibowli", "Madhapur", "Kompally"},
    {"Chennai", "Kancheepuram", "Chengalpattu"},
    {"Kolkata", "Howrah", "Salt Lake", "Rajarhat", "New Town"},
    {"Pune", "Pimpri", "Chinchwad"},
    {"Surat", "Vapi", "Navsari"},
    {"Ahmedabad", "Gandhinagar", "Anand"},
    {"Coimbatore", "Tiruppur", "Erode"},
    {"Kochi", "Ernakulam", "Alappuzha"},
    {"Manipal", "Udupi", "Mangaluru"},
    {"Siliguri", "Jalpaiguri", "Darjeeling"},
]


def same_region(a: str | None, b: str | None) -> bool:
    """True when two canonical cities belong to the same metro region."""
    if not a or not b or a.lower() == b.lower():
        return False
    al, bl = a.lower(), b.lower()
    return any(al in {c.lower() for c in r} and bl in {c.lower() for c in r} for r in _REGIONS)
