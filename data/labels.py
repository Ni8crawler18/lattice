"""Human-verified labels for the real MICR candidate pairs.

PROVENANCE, stated plainly:
  - The ADDRESSES are real, unmodified, from Razorpay's open IFSC dataset.
  - The LABELS are ours, assigned by reading each pair. They are not derived
    from the dataset, because MICR is NOT reliable ground truth: of 18 pairs
    sharing a MICR code, only 8 are actually the same building. The rest are
    stale records, bank mergers, or branches that relocated.

That finding matters on its own -- it is precisely the deduplication problem
this product solves, visible inside a production banking dataset.

Index refers to position in data/real_pairs_raw.json (micr_same_branch kind).
"""

# True = same physical building. Reasoning recorded so the call can be audited.
MICR_LABELS = {
    0:  (False, "Prem Heights, Ajit Nagar vs SCO 121, Urban Estate Phase 2 — two Patiala branches"),
    1:  (False, "LDA Colony, Kanpur Road vs Alambagh — different Lucknow localities"),
    2:  (True,  "Madhavleela Complex, Maskasath Square, Itwari — same, components reordered"),
    3:  (True,  "Plot 7&7A Mysari Chambers, Saraswathi Colony, Lothukunta — spelling variance only"),
    4:  (True,  "GMCB Bhavan, Plot 12, Sector 9, Gandhidham — B adds 'Banking Circle' and district"),
    5:  (False, "Sahyog Plot 33, Telephone Sq vs Shreeji House Plot 39, Khamla Sq"),
    6:  (True,  "Door 3-116, 1st floor, Hanuman Nagar Colony, Chaitanyapuri — spacing variance"),
    7:  (False, "Sukhmani, Ganjmal vs Shop 6/7 Balaji Shankul, Amrutdham"),
    8:  (True,  "Abhay Prashal, 10, Race Course Road, Indore — pure component reorder"),
    9:  (True,  "Both opposite K.V. School at/behind Dhruv Complex, Una — same site, ambiguous wording"),
    10: (True,  "Sharma Building, Old Post Office Road, Nehru Ward, Hinganghat — B adds chowk + PIN"),
    11: (False, "Achyut Arcade, Jubilee Circle vs SDM College campus, Vijaya Road"),
    12: (False, "M.I.A. Alwar vs Gol Market, Rajgarh — same district, different towns"),
    13: (False, "B.O. Farrukh Nagar vs B.O. S.P. Majri — two branch offices"),
    14: (True,  "7-1-72/73/74 Gayatri Towers, Tahasil Chowrasta, Jagtial — transliteration variance"),
    15: (False, "IDBI Building, Panampilly Nagar vs Sea Queen Bldg, Edapally"),
    16: (False, "M J Mall, Railway Road vs 637 Laxman Jhoola Road, Rishikesh"),
    17: (False, "Kumaranalloor, Perubaikod PO vs Noyaplaza, Kalathipady, Vadavathoor PO"),
}

MICR_POSITIVES = sum(1 for v, _ in MICR_LABELS.values() if v)
MICR_TOTAL = len(MICR_LABELS)
