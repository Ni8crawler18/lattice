"""Seed address set for Lattice.

Patterns are drawn from how Indian addresses are actually written: landmark-led,
inconsistent component order, abbreviations, script mixing, colloquial locality
names. Records sharing a `truth` id are the SAME physical location written
differently -- that is the ground truth for Layer 1 entity resolution.

NOTE: this is a hand-built seed set, not scraped production data. Say so if asked.
Swap in real listings before the pitch if there is time.
"""

SEED = [
    # --- Pune: same house, four ways -------------------------------------
    dict(id="p1", truth="PUNE_A",
         raw="Ganesh mandir ke peeche, blue gate wala ghar, opp SBI ATM, Kothrud, Pune 411038"),
    dict(id="p2", truth="PUNE_A",
         raw="Blue gate house, behind Ganesh Temple, near State Bank ATM, Kothrood, Pune - 411 038"),
    dict(id="p3", truth="PUNE_A",
         raw="गणेश मंदिराच्या मागे, निळा गेट, एसबीआय एटीएम समोर, कोथरूड, पुणे ४११०३८"),
    dict(id="p4", truth="PUNE_A",
         raw="Nr SBI atm, Kothrud, behind ganesh mndir, blue gate, Pune"),

    # --- Bengaluru: same flat, three ways --------------------------------
    dict(id="b1", truth="BLR_A",
         raw="2nd cross, 4th main, near Ayyappa temple, behind Reliance Fresh, BTM 2nd stage, B'lore 560076"),
    dict(id="b2", truth="BLR_A",
         raw="#12, 4th Main Road, 2nd Cross, BTM Layout 2nd Stage, Bengaluru 560076, opposite Ayyappa Temple"),
    dict(id="b3", truth="BLR_A",
         raw="4th main 2nd cross btm 2nd stage bangalore near ayyappa temple reliance fresh backside"),

    # --- Chennai: Tamil + Latin, same door ------------------------------
    dict(id="c1", truth="CHN_A",
         raw="No 7, Bharathi Street, Ashok Nagar, opposite to Saravana Stores, Chennai 600083"),
    dict(id="c2", truth="CHN_A",
         raw="7, பாரதி தெரு, அசோக் நகர், சரவணா ஸ்டோர்ஸ் எதிரில், சென்னை 600083"),

    # --- Delhi: same house, gali-style ----------------------------------
    dict(id="d1", truth="DEL_A",
         raw="H.No 45, Gali No 6, Shakarpur, near Laxmi Nagar metro station, Delhi-110092"),
    dict(id="d2", truth="DEL_A",
         raw="45, gali no. 6 shakarpur, laxmi nagar metro ke paas, new delhi 110092"),

    # --- Distinct locations (must NOT collapse) --------------------------
    dict(id="x1", truth="PUNE_B",
         raw="Flat 302, Shivneri Apartments, Karve Road, Kothrud, Pune 411038"),
    dict(id="x2", truth="BLR_B",
         raw="No 88, 4th Main, BTM 1st Stage, Bengaluru 560029, near Udupi Hotel"),
    dict(id="x3", truth="DEL_B",
         raw="H.No 45, Gali No 6, Krishna Nagar, near Laxmi Nagar metro, Delhi 110051"),

    # --- Hard singletons: landmark-only, no house number -----------------
    dict(id="s1", truth="HYD_A",
         raw="Beside Ratnadeep supermarket, above Kotak bank, Madhapur, Hyd"),
    dict(id="s2", truth="KOL_A",
         raw="৩২এ, রাসবিহারী এভিনিউ, কালীঘাট মেট্রোর কাছে, কলকাতা ৭০০০২৬"),
    dict(id="s3", truth="LKO_A",
         raw="Hanuman mandir ke saamne wali gali, teesra makan, Aminabad, Lucknow"),
    dict(id="s4", truth="AHM_A",
         raw="B-14, Swagat Flats, Naranpura char rasta pase, Ahmedabad 380013"),
    dict(id="s5", truth="JAI_A",
         raw="Plot 22, near Jain mandir, Malviya Ngr sector 4, Jaipur, Raj - 302017"),
    dict(id="s6", truth="MUM_A",
         raw="Room no 4, chawl no 2, Dr Ambedkar Rd, behind Sena bhavan, Dadar East, Mumbai 400014"),
]


def pairs():
    """All (a, b, same_location?) combinations -- Layer 1 evaluation set."""
    out = []
    for i in range(len(SEED)):
        for j in range(i + 1, len(SEED)):
            out.append((SEED[i], SEED[j], SEED[i]["truth"] == SEED[j]["truth"]))
    return out
