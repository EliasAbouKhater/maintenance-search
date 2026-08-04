"""
Hand-curated phrase→expansion map for the lexical (keyword) engine.

When a technician query contains any of the LHS patterns, the RHS tokens are
appended to the query token list — a form of manual synonym expansion.
This is what lets a query like "not turning on" match documents that only
say "boot failure" or "won't start".

Adding entries is cheap and boosts recall on paraphrased queries. Removing
entries is safe. Editing regex requires care because a bad pattern silently
matches everything.
"""

PHRASE_MAP = {
    r"not turning on|won'?t (turn|boot|start|power)":    "boot power startup",
    r"screen (is |)blank|black screen|no display":       "display blank black screen",
    r"no power|power (is |)out|power fail":              "power supply failure",
    r"communication (error|fail|lost|problem)":          "communication link error sas",
    r"sas (error|fail|link)":                            "sas link communication",
    r"memory (error|fail|clear)":                        "ram memory clear",
    r"coin (jammed?|stuck|problem)":                     "coin jam hopper",
    r"ticket (jammed?|stuck|not printing)":              "ticket printer jam",
    r"card reader (not working|fail|error)":             "card reader failure",
    r"network (down|disconnected?|problem|error)":       "network connection switch",
    r"camera (blurry|out of focus|dark|bright)":         "camera focus exposure",
    r"air con|ac (not working|fail|problem)":            "ac hvac cooling",
    r"touch screen|touch (not working|unresponsive)":    "touchscreen calibration",
    r"door (alarm|sensor|open)":                         "door sensor alarm",
    r"overheat|overheating|too hot":                     "temperature overheat cooling",
    r"jackpot (error|fail|not paying)":                  "jackpot payout error",
    r"bill acceptor|note acceptor|cash (jammed?|stuck)": "bill acceptor note jam",
}

STOP_WORDS = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "shall", "can", "to", "of", "in", "on", "at",
    "by", "for", "with", "about", "from", "into", "through", "what", "how",
    "why", "when", "where", "which", "who", "whom", "i", "we", "you", "he",
    "she", "they", "it", "this", "that", "these", "those", "my", "our", "your",
    "their", "any", "some", "all", "just", "also", "and", "or", "but", "if",
    "then", "than", "not", "no", "yes", "ok", "please", "help", "issue",
    "problem", "question", "tell", "me", "find", "show", "give", "look",
    "check", "see", "know", "need", "want", "ask",
}
