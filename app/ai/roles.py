"""Domain knowledge used by the matcher: role profiles, skill implications and
substitutable-skill groups. Pure data + tiny helpers, no framework imports.

Why this exists: matching on literal skill strings alone misses obvious fits
("Django" implies Python; PyTorch is a close substitute for TensorFlow) and a
role name like "Backend Developer Intern" rarely appears verbatim in a title.
"""
import re

from .skills import ROLES

# ---------------------------------------------------------------- skill graph
# user HAS key  ->  also counts (at IMPLIED_CREDIT) for each listed skill.
IMPLIES: dict[str, set[str]] = {
    "Django": {"Python"}, "Flask": {"Python"}, "FastAPI": {"Python", "REST APIs"},
    "Pandas": {"Python", "Data Analysis"}, "NumPy": {"Python"}, "Matplotlib": {"Python", "Data Visualization"},
    "Seaborn": {"Python", "Data Visualization"}, "Jupyter": {"Python"},
    "Scikit-learn": {"Python", "Machine Learning"},
    "TensorFlow": {"Python", "Machine Learning", "Deep Learning"},
    "PyTorch": {"Python", "Machine Learning", "Deep Learning"},
    "Keras": {"Python", "Machine Learning", "Deep Learning"},
    "Deep Learning": {"Machine Learning"}, "NLP": {"Machine Learning"},
    "Computer Vision": {"Machine Learning"}, "OpenCV": {"Computer Vision"},
    "Hugging Face": {"NLP", "Machine Learning", "Python"},
    "LangChain": {"LLMs", "Generative AI", "Python"}, "LLMs": {"Generative AI"},
    "Prompt Engineering": {"Generative AI"}, "MLOps": {"Machine Learning"},
    "Data Science": {"Machine Learning", "Statistics", "Data Analysis"},
    "React": {"JavaScript", "HTML", "CSS"}, "Next.js": {"React", "JavaScript"},
    "Angular": {"TypeScript", "JavaScript", "HTML", "CSS"}, "Vue.js": {"JavaScript", "HTML", "CSS"},
    "Redux": {"React", "JavaScript"}, "TypeScript": {"JavaScript"},
    "Node.js": {"JavaScript"}, "Express.js": {"Node.js", "JavaScript", "REST APIs"},
    "React Native": {"React", "JavaScript"}, "Tailwind CSS": {"CSS"}, "Bootstrap": {"CSS", "HTML"},
    "Spring Boot": {"Java", "REST APIs"}, ".NET": {"C#"}, "Flutter": {"Dart"},
    "Kotlin Multiplatform": {"Kotlin"},
    "MySQL": {"SQL"}, "PostgreSQL": {"SQL"}, "SQLite": {"SQL"}, "Oracle": {"SQL"},
    "MongoDB": {"NoSQL"}, "Redis": {"NoSQL"}, "Firebase": {"NoSQL"},
    "Kubernetes": {"Docker"}, "Terraform": {"DevOps"}, "Jenkins": {"CI/CD", "DevOps"},
    "Ansible": {"DevOps"}, "Docker": {"DevOps"},
    "Selenium": {"Software Testing", "Test Automation"}, "Cypress": {"Software Testing", "Test Automation"},
    "Playwright": {"Software Testing", "Test Automation"}, "JUnit": {"Software Testing"},
    "Test Automation": {"Software Testing"}, "Postman": {"REST APIs"},
    "Penetration Testing": {"Cybersecurity"}, "Ethical Hacking": {"Cybersecurity"},
    "Network Security": {"Cybersecurity"}, "SIEM": {"Cybersecurity"}, "Cryptography": {"Cybersecurity"},
    "Burp Suite": {"Penetration Testing", "Cybersecurity"}, "Metasploit": {"Penetration Testing", "Cybersecurity"},
    "Nmap": {"Network Security"}, "Wireshark": {"Network Security"}, "Kali Linux": {"Linux", "Ethical Hacking"},
    "Power BI": {"Data Visualization"}, "Tableau": {"Data Visualization"},
    "Solidity": {"Blockchain"}, "Ethereum": {"Blockchain"}, "Web3": {"Blockchain"},
    "Arduino": {"Embedded Systems"}, "Raspberry Pi": {"Embedded Systems"}, "RTOS": {"Embedded Systems"},
    "Verilog": {"Embedded Systems"}, "IoT": {"Embedded Systems"},
    "Data Structures": {"Algorithms"}, "Algorithms": {"Data Structures"},
    "SEO": {"Digital Marketing"}, "Social Media Marketing": {"Digital Marketing"},
    "Email Marketing": {"Digital Marketing"}, "Google Analytics": {"Digital Marketing"},
    "Copywriting": {"Content Writing"}, "Technical Writing": {"Content Writing"},
    "Wireframing": {"UI/UX Design"}, "Prototyping": {"UI/UX Design"}, "Figma": {"UI/UX Design"},
    "Adobe XD": {"UI/UX Design"},
}
IMPLIED_CREDIT = 0.85

# Substitutable skills: knowing one gives partial credit for another in the same group.
RELATED_GROUPS: list[tuple[set[str], float]] = [
    ({"React", "Angular", "Vue.js", "Next.js"}, 0.55),
    ({"TensorFlow", "PyTorch", "Keras"}, 0.65),
    ({"MySQL", "PostgreSQL", "SQLite", "Oracle", "SQL"}, 0.7),
    ({"MongoDB", "NoSQL", "Firebase", "Redis"}, 0.5),
    ({"AWS", "Azure", "GCP"}, 0.6),
    ({"Tableau", "Power BI", "Excel"}, 0.5),
    ({"Django", "Flask", "FastAPI"}, 0.65),
    ({"Django", "Flask", "FastAPI", "Node.js", "Express.js", "Spring Boot", ".NET", "PHP", "Ruby"}, 0.35),
    ({"Java", "C#", "Kotlin", "C++", "Go", "Rust", "Scala"}, 0.3),
    ({"Python", "R", "MATLAB"}, 0.25),
    ({"Selenium", "Cypress", "Playwright"}, 0.65),
    ({"Figma", "Adobe XD", "Photoshop", "Canva", "Illustrator"}, 0.5),
    ({"Flutter", "React Native", "Android", "iOS"}, 0.4),
    ({"Pandas", "NumPy", "Matplotlib", "Seaborn"}, 0.5),
    ({"Docker", "Kubernetes", "Terraform", "Ansible", "Jenkins", "CI/CD", "DevOps"}, 0.4),
    ({"Penetration Testing", "Ethical Hacking", "Network Security", "Cybersecurity", "SIEM"}, 0.5),
    ({"Machine Learning", "Deep Learning", "Data Science", "NLP", "Computer Vision", "LLMs", "Generative AI"}, 0.4),
    ({"SEO", "Digital Marketing", "Social Media Marketing", "Email Marketing", "Content Writing", "Copywriting"}, 0.4),
    ({"Spark", "Hadoop", "ETL"}, 0.45),
]

# Skills that nearly every listing mentions: they say little about fit, so count for less.
GENERIC_SKILLS = {"Git", "Agile", "JIRA", "Excel", "OOP", "Linux", "Canva", "Bash"}
GENERIC_WEIGHT = 0.5
TITLE_WEIGHT = 2.0  # a skill named in the job title is the headline requirement


# ---------------------------------------------------------------- role profiles
class RoleProfile:
    __slots__ = ("name", "title_re", "desc_re", "core", "generic")

    def __init__(self, name, title, desc, core, generic=False):
        self.name = name
        self.title_re = re.compile(title)
        self.desc_re = re.compile(desc or title)
        self.core = tuple(core)
        self.generic = generic  # generic roles only match titles no specific role claims


_P = RoleProfile
_BASE_PROFILES: list[RoleProfile] = [
    _P("Software Development Intern",
       r"software|\bsde\b|programmer|developer|\bengineer|coding|application dev",
       r"software (development|engineering)|\bsde\b|programming",
       ["Data Structures", "Algorithms", "OOP", "Git", "Python", "Java"], generic=True),
    _P("Frontend Developer Intern",
       r"front[\s-]?end|\bui (developer|engineer|intern)|react(\.?js)?\b|angular|\bvue\b|next\.?js",
       r"front[\s-]?end|user interfaces?|responsive (web|design)",
       ["JavaScript", "React", "HTML", "CSS", "TypeScript"]),
    _P("Backend Developer Intern",
       r"back[\s-]?end|server[\s-]?side|\bapi (developer|engineer|intern)|node(\.?js)?\b|django|flask|spring|laravel",
       r"back[\s-]?end|server[\s-]?side|\bapis?\b|microservices?",
       ["Python", "Java", "Node.js", "SQL", "REST APIs", "Django", "Spring Boot"]),
    _P("Full-Stack Developer Intern",
       r"full[\s-]?stack|\bmern\b|\bmean\b|web (developer|development|dev)\b",
       r"full[\s-]?stack|front[\s-]?end and back[\s-]?end",
       ["JavaScript", "React", "Node.js", "HTML", "CSS", "SQL", "MongoDB"]),
    _P("Mobile App Developer Intern",
       r"mobile|android|\bios\b|flutter|react native|\bapp (developer|development)",
       r"mobile (app|application)|android|\bios\b|flutter",
       ["Android", "iOS", "Flutter", "React Native", "Kotlin", "Swift", "Dart"]),
    _P("AI/ML Intern",
       r"\bai\b|\bml\b|machine learning|artificial intelligence|deep learning|\bnlp\b|computer vision|generative|\bllms?\b|genai|\bai\s*/\s*ml",
       r"machine learning|deep learning|neural|\bnlp\b|computer vision|\bllms?\b|generative ai",
       ["Python", "Machine Learning", "Deep Learning", "TensorFlow", "PyTorch", "Scikit-learn", "NLP", "Pandas", "NumPy"]),
    _P("Data Science Intern",
       r"data scien",
       r"data scien|predictive model|statistical model",
       ["Python", "Pandas", "NumPy", "Machine Learning", "Statistics", "SQL", "Data Visualization", "Scikit-learn"]),
    _P("Data Analyst Intern",
       r"data analy|business intelligence|\bbi (analyst|developer|intern)|analytics|power bi|tableau|\bmis\b",
       r"data analy|dashboards?|business intelligence|reporting|\bkpis?\b",
       ["SQL", "Excel", "Power BI", "Tableau", "Python", "Data Visualization", "Data Analysis", "Statistics"]),
    _P("Data Engineering Intern",
       r"data engine|etl|pipeline|big data|spark|hadoop|data warehouse",
       r"data engine|etl|pipeline|data warehousing",
       ["SQL", "Python", "ETL", "Spark", "PostgreSQL", "MongoDB", "Data Pipelines"]),
    _P("Cybersecurity Intern",
       r"cyber|security|infosec|penetration|pentest|\bsoc\b|\bvapt\b|ethical hack|threat|\bsiem\b",
       r"cyber|security|vulnerabilit|penetration|threat|incident response",
       ["Cybersecurity", "Network Security", "Penetration Testing", "Linux", "Ethical Hacking", "SIEM", "Cryptography"]),
    _P("Cloud / DevOps Intern",
       r"devops|cloud|\bsre\b|site reliability|infrastructure|kubernetes|\baws\b|azure|\bgcp\b|platform engineer",
       r"devops|cloud|ci/cd|infrastructure|deployment|containers?",
       ["AWS", "Docker", "Kubernetes", "Linux", "CI/CD", "Terraform", "Git", "Jenkins"]),
    _P("QA / Testing Intern",
       r"\bqa\b|quality (assurance|engineer|analyst)|\btest(er|ing)?\b|\bsdet\b|automation test",
       r"\bqa\b|quality assurance|test (cases?|plans?|automation)|testing",
       ["Software Testing", "Selenium", "Test Automation", "JIRA", "Agile", "Postman"]),
    _P("UI/UX Design Intern",
       r"ui\s*/?\s*ux|\bux\b|user (experience|interface)|product design|graphic|visual design|\bdesign(er)?\b|figma|illustrat",
       r"ui\s*/?\s*ux|wireframe|prototype|user research|design system",
       ["UI/UX Design", "Figma", "Wireframing", "Prototyping", "Adobe XD", "Photoshop"]),
    _P("Graphic Design Intern",
       r"graphic design|visual designer|banner|canva|photoshop|illustrator|poster",
       r"graphic design|branding|illustrations?|photoshop|canva",
       ["Photoshop", "Illustrator", "Canva", "UI/UX Design", "Figma"]),
    _P("Product Design Intern",
       r"product design|interaction design|industrial design",
       r"product design|user research|prototyping|design system",
       ["Figma", "UI/UX Design", "Prototyping", "Wireframing", "User Research"]),
    _P("Motion Graphics Intern",
       r"motion graphic|after effects|animation|animator|video edit",
       r"motion graphics?|animation|after effects|video editing",
       ["After Effects", "Premiere Pro", "Animation", "Graphic Design"]),
    _P("Product Management Intern",
       r"product (management|manager|analyst|intern|operations)|\bapm\b|\bpm intern",
       r"product (management|roadmap|strategy)|user stories|\bprd\b|roadmap",
       ["Product Management", "Agile", "JIRA", "Business Analysis", "Data Analysis", "Market Research"]),
    _P("Business Analyst Intern",
       r"business analy|\bba\b|process analyst|strategy|consult|operations analyst|business development",
       r"business analy|requirements gathering|stakeholders?|process improvement",
       ["Business Analysis", "Excel", "SQL", "Data Analysis", "Power BI", "JIRA", "Agile"]),
    _P("Operations Intern",
       r"operation|logistics|supply chain|inventory|process management",
       r"operations?|process optimization|logistics",
       ["Operations", "Excel", "Problem Solving", "Process Management"]),
    _P("Strategy Intern",
       r"strategy|strategic|corporate development|business strategy",
       r"strategy|market analysis|growth strategy",
       ["Business Analysis", "Market Research", "Financial Modeling", "Excel"]),
    _P("Consulting Intern",
       r"consulting|consultant|advisory|management consult",
       r"consulting|problem solving|client management",
       ["Problem Solving", "Business Analysis", "Communication", "Excel", "PowerPoint"]),
    _P("Supply Chain Intern",
       r"supply chain|procurement|vendor management|inventory",
       r"supply chain|logistics|procurement|vendor",
       ["Operations", "Excel", "Data Analysis", "Negotiation"]),
    _P("Finance Intern",
       r"finance|financial|accounting|accountant|tally|auditing",
       r"financial|accounting|budgeting|auditing|financial analysis",
       ["Finance", "Accounting", "Excel", "Financial Modeling", "Tally"]),
    _P("Investment Banking Intern",
       r"investment bank|\bib\b|valuation|m&a|mergers|capital markets",
       r"valuation|dcf|m&a|financial modeling|investment banking",
       ["Financial Modeling", "Valuation", "Excel", "Accounting", "Corporate Finance"]),
    _P("Equity Research Intern",
       r"equity research|financial analyst|stock market|portfolio",
       r"equity research|earnings|financial modeling|industry analysis",
       ["Financial Modeling", "Equity Research", "Excel", "Data Analysis"]),
    _P("Digital Marketing Intern",
       r"marketing|\bseo\b|social media|growth|brand|\bsem\b|performance marketing|e-?mail marketing",
       r"digital marketing|\bseo\b|social media|campaigns?|google ads|performance marketing",
       ["Digital Marketing", "SEO", "Social Media Marketing", "Google Analytics", "Email Marketing", "Content Writing", "Canva"]),
    _P("Content Writing Intern",
       r"content|copywrit|writer|writing|blog|editorial|journalis",
       r"content (creation|writing)|copywrit|blog|articles?|editing",
       ["Content Writing", "Copywriting", "SEO", "Technical Writing", "Digital Marketing"]),
    _P("Social Media Intern",
       r"social media|instagram|linkedin|twitter|community manager",
       r"social media|content creation|engagement|campaigns",
       ["Social Media Marketing", "Content Writing", "Canva", "Digital Marketing"]),
    _P("SEO Intern",
       r"\bseo\b|search engine optimization|backlink|keyword research",
       r"seo|keywords?|google search console|ranking",
       ["SEO", "Google Analytics", "Content Writing", "Digital Marketing"]),
    _P("Brand Management Intern",
       r"brand|branding|brand manager|public relations|\bpr\b",
       r"branding|market positioning|brand identity",
       ["Brand Management", "Marketing", "Communication", "Creative Thinking"]),
    _P("Growth Marketing Intern",
       r"growth (marketing|hacker|lead)|retention marketing|acquisition",
       r"growth marketing|funnels?|conversion rate|analytics",
       ["Digital Marketing", "Google Analytics", "Data Analysis", "A/B Testing"]),
    _P("Research Intern",
       r"research|r&d|researcher|academic|literature review",
       r"research methodology|experiment|analysis|literature",
       ["Research", "Data Analysis", "Python", "Critical Thinking"]),
    _P("Data Research Intern",
       r"data research|survey|market intelligence",
       r"data collection|quantitative research|qualitative research",
       ["Data Analysis", "Excel", "SQL", "Research"]),
    _P("Policy Research Intern",
       r"policy|public policy|governance|socioeconomic",
       r"policy analysis|regulatory|advocacy|research",
       ["Policy Analysis", "Research", "Technical Writing", "Communication"]),
    _P("HR Intern",
       r"\bhr\b|human resources|people ops|talent acquisition|employee engagement",
       r"human resources|recruiting|onboarding|employee relations",
       ["Human Resources", "Recruitment", "Communication", "Excel", "Interpersonal Skills"]),
    _P("Recruitment Intern",
       r"recruitment|recruiter|talent sourcing|interviewing",
       r"sourcing candidates|screening|hiring pipeline",
       ["Recruitment", "Sourcing", "Communication", "Interviewing"]),
    _P("Legal Intern",
       r"legal|law|paralegal|contracts?|compliance|intellectual property|\bipr\b",
       r"legal research|contract drafting|due diligence|compliance",
       ["Legal Research", "Contract Drafting", "Compliance", "Critical Thinking"]),
    _P("Blockchain Developer Intern",
       r"blockchain|web3|solidity|smart contract|crypto|ethereum|\bdapps?\b",
       r"blockchain|web3|smart contracts?|solidity|ethereum",
       ["Blockchain", "Solidity", "Ethereum", "Web3", "JavaScript", "Cryptography"]),
    _P("Web3 / Blockchain Intern",
       r"blockchain|web3|solidity|smart contract|crypto|ethereum|\bdapps?\b",
       r"blockchain|web3|smart contracts?|solidity|ethereum",
       ["Blockchain", "Solidity", "Ethereum", "Web3", "Cryptography"]),
    _P("Embedded Systems Intern",
       r"embedded|firmware|\biot\b|\brtos\b|microcontroller|\bvlsi\b|arduino|hardware",
       r"embedded|firmware|microcontrollers?|\biot\b|\brtos\b",
       ["Embedded Systems", "C", "C++", "IoT", "Arduino", "Raspberry Pi", "RTOS"]),
    _P("IoT Intern",
       r"\biot\b|internet of things|sensors?|microcontroller|raspberry pi",
       r"iot|sensors|telemetry|hardware-software integration",
       ["IoT", "Embedded Systems", "C", "Python", "Arduino", "Raspberry Pi"]),
    _P("Game Development Intern",
       r"game (dev|developer|development)|unity|unreal engine|godot",
       r"game mechanics|3d rendering|unity|unreal",
       ["Game Development", "Unity", "C#", "C++", "Unreal Engine"]),
    _P("AR/VR Developer Intern",
       r"ar\s*/?\s*vr|augmented reality|virtual reality|metaverse|oculus|webxr",
       r"spatial computing|3d models|unity|arcore|arkit",
       ["Unity", "AR/VR", "C#", "3D Modeling", "Computer Vision"]),
    _P("Prompt Engineering Intern",
       r"prompt engine|llm|generative ai|chatgpt|claude|prompting",
       r"prompt design|few-shot|llm orchestration|evaluations",
       ["Prompt Engineering", "LLMs", "Generative AI", "Python"]),
    _P("MLOps Intern",
       r"mlops|machine learning operations|model deployment|kubeflow|mlflow",
       r"model serving|ml pipelines|monitoring|ci/cd for ml",
       ["MLOps", "Python", "Docker", "Kubernetes", "Machine Learning", "CI/CD"]),
    _P("Technical Writing Intern",
       r"technical (writer|writing)|developer documentation|\bdocs\b|api docs",
       r"api documentation|user manuals|guides|markdown",
       ["Technical Writing", "Documentation", "Git", "Markdown", "REST APIs"]),
    _P("Customer Success Intern",
       r"customer (success|support|experience)|\bcsm\b|client relations",
       r"customer onboarding|retention|ticketing|communication",
       ["Customer Support", "Communication", "Problem Solving", "CRM"]),
    _P("Sales Intern",
       r"sales|lead generation|inside sales|account executive",
       r"prospecting|cold calling|sales pipeline|closing deals",
       ["Sales", "Communication", "Negotiation", "Lead Generation", "CRM"]),
    _P("Business Development Intern",
       r"business development|\bbde\b|\bbda\b|partnership|client acquisition",
       r"strategic partnerships|outreach|market expansion",
       ["Business Development", "Communication", "Sales", "Market Research", "Negotiation"]),
]

PROFILES: dict[str, RoleProfile] = {p.name: p for p in _BASE_PROFILES}

# Ensure every role in ROLES has a profile even if new ones are added
for _role in ROLES:
    if _role not in PROFILES:
        _clean_kw = re.sub(r"\s+intern$", "", _role, flags=re.IGNORECASE).strip().lower()
        PROFILES[_role] = _P(
            _role,
            rf"\b{re.escape(_clean_kw)}\b",
            rf"\b{re.escape(_clean_kw)}\b",
            ["Communication", "Problem Solving", "Critical Thinking"],
        )

_RELATED_PAIRS = {
    ("Software Development Intern", "Frontend Developer Intern"): 0.7,
    ("Software Development Intern", "Backend Developer Intern"): 0.7,
    ("Software Development Intern", "Full-Stack Developer Intern"): 0.8,
    ("Software Development Intern", "Mobile App Developer Intern"): 0.6,
    ("Software Development Intern", "AI/ML Intern"): 0.4,
    ("Software Development Intern", "Cloud / DevOps Intern"): 0.4,
    ("Software Development Intern", "Blockchain Developer Intern"): 0.4,
    ("Software Development Intern", "Embedded Systems Intern"): 0.4,
    ("Software Development Intern", "QA / Testing Intern"): 0.4,
    ("Frontend Developer Intern", "Full-Stack Developer Intern"): 0.75,
    ("Backend Developer Intern", "Full-Stack Developer Intern"): 0.75,
    ("Frontend Developer Intern", "Backend Developer Intern"): 0.35,
    ("Frontend Developer Intern", "UI/UX Design Intern"): 0.4,
    ("Mobile App Developer Intern", "Frontend Developer Intern"): 0.4,
    ("Mobile App Developer Intern", "Full-Stack Developer Intern"): 0.4,
    ("AI/ML Intern", "Data Science Intern"): 0.75,
    ("Data Science Intern", "Data Analyst Intern"): 0.6,
    ("AI/ML Intern", "Data Analyst Intern"): 0.35,
    ("Backend Developer Intern", "Cloud / DevOps Intern"): 0.4,
    ("Cloud / DevOps Intern", "Cybersecurity Intern"): 0.35,
    ("Product Management Intern", "Business Analyst Intern"): 0.5,
    ("Product Management Intern", "UI/UX Design Intern"): 0.35,
    ("Business Analyst Intern", "Data Analyst Intern"): 0.45,
    ("Digital Marketing Intern", "Content Writing Intern"): 0.5,
}
RELATED_ROLES: dict[str, dict[str, float]] = {}
for (_a, _b), _w in _RELATED_PAIRS.items():
    RELATED_ROLES.setdefault(_a, {})[_b] = _w
    RELATED_ROLES.setdefault(_b, {})[_a] = _w
RELATED_ROLES = {k: v for k, v in RELATED_ROLES.items()}

_SPECIFIC = [p for p in PROFILES.values() if not p.generic]
_GENERIC = [p for p in PROFILES.values() if p.generic]


def roles_in_title(title: str | None) -> set[str]:
    """Roles whose title pattern matches. Generic roles apply only when no specific role does."""
    t = (title or "").lower()
    hits = {p.name for p in _SPECIFIC if p.title_re.search(t)}
    if not hits:
        hits = {p.name for p in _GENERIC if p.title_re.search(t)}
    return hits


def resolve_roles(text: str | None) -> set[str]:
    """Map a student's role (curated name or free text) to curated roles; empty set if unknown."""
    t = (text or "").strip().lower()
    if not t:
        return set()
    for name in PROFILES:
        if name.lower() == t:
            return {name}
    return roles_in_title(t)
