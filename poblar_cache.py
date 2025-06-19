import os
import json
from backend.mtg_core import buscar_en_scryfall, buscar_en_magic_api, cargar_cache, guardar_cache

# Lista de cartas populares de Magic: The Gathering
cartas_populares = [
    "Black Knight", "Ancestral Recall", "Time Walk", "Mox Emerald", "Mox Sapphire",
    "Mox Ruby", "Mox Jet", "Mox Pearl", "The Power Nine", "Power Nine",
    "Jace the Mind Sculptor", "Liliana of the Veil", "Mana Crypt", "Umez Etenzo",
    "Sol Ring", "Bazaar of Baghdad", "Underground Sea", "Force of Will", "Brainstorm",
    "Black Lotus", "Island", "Mountain", "Forest", "Plains", "Swamp", 
    "Murktide Regent", "Ancestral Mask", "Tarmogoyf", "Wasteland", "Daze", 
    "Counterspell", "Swords to Plowshares", "Stoneforge Mystic", "Sensei's Divining Top",
    "Deathrite Shaman", "Delver of Secrets", "Ponder", "Red Elemental Blast", 
    "Pyroblast", "Blue Elemental Blast", "Vampire Hexmage", "Thalia Guardian of Thraben",
    "Choke", "Back to Basics", "Library of Alexandria", "Strip Mine", "Windswept Heath",
    "Verdant Catacombs", "Marsh Flats", "Arid Mesa", "Scalding Tarn", "Polluted Delta",
    "Underground River", "Mana Confluence", "Command Tower", "Relentless Rhombus", "Seat of the Synod",
    "Chrome Mox", "Mishra's Workshop", "Grim Monolith", "Basalt Monolith", "Black Vise",
    "Mox Diamond", "Imperial Recruiter", "Serra Avenger", "Serra Angel", "Volcanic Island",
    "Tundra", "Scrubland", "Aqueduct", "Taiga", "Badlands", "Bayou", "Plateau", "Savannah",
    "Scrubsaber Tiger", "Birds of Paradise", "Elvish Spirit Guide", "Fry", "Fireball",
    "Ancestral Vision", "Opt", "Serum Visions", "Gitaxian Probe", "Inquisition of Kozilek",
    "Thoughtseize", "Brainstorm", "Ponder", "Fact or Fiction", "Counterbalance",
    "Spell Pierce", "Flusterclaw", "True-Name Nemesis", "Leonin Relic", "Chrome Mox",
    "Underworld Connections", "Echoing Truth", "Vendilion Clique", "Stoneforge Mystic",
    "Ulamog", "Emrakul", "Progenitus", "Karakas", "Celestial Colonnade", "Tolarian Academy",
    "Mana Vault", "Mishra's Factory", "City in a Bottle", "Mana Battery", "Mana Severance",
    "Mana Reflection", "Mana Echoes", "Mana Crypt", "Mana Vault", "Mana Drain", "Mana Shortage"
]

# Carpeta del caché
os.makedirs("data", exist_ok=True)

# Limpiar caché actual si existe
cache = cargar_cache()
for carta in cartas_populares:
    resultados = buscar_en_scryfall(carta)
    if resultados:
        cache[carta.lower()] = resultados
        print(f"💾 Cartas guardadas: {len(resultados)} versiones de `{carta}`")

guardar_cache(cache)
print("🎉 Caché poblado con éxito.")
