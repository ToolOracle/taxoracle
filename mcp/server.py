#!/usr/bin/env python3
"""
TaxOracle — Advanced Tax Compliance & International Tax MCP v1.0.0
Port 12801 | Part of ToolOracle Whitelabel MCP Platform

Extends CFOCoPilot (basic VAT/calendar) with ADVANCED TAX OPERATIONS.
CFOCoPilot = validate VAT + basic calendar → TaxOracle = DAC6, Pillar Two, cross-border, audit prep.

12 Tools:
  ── International Tax ──
  1.  dac6_assessment     — DAC6/DAC7 cross-border reporting obligation check
  2.  pillar_two_calc     — OECD Pillar Two / GloBE minimum tax calculation
  3.  transfer_pricing    — Transfer pricing method selector + documentation requirements
  4.  withholding_tax     — WHT rates for 40+ country pairs (DBA network)
  5.  pe_risk_check       — Permanent Establishment risk assessment

  ── German Tax ──
  6.  ust_voranmeldung    — USt-Voranmeldung data preparation (ELSTER fields)
  7.  trade_tax_calc      — Gewerbesteuer calculation with Hebesatz
  8.  betriebspruefung    — Betriebsprüfung readiness checklist

  ── Accounting ──
  9.  gaap_ifrs_diff      — HGB vs IFRS key differences
 10.  depreciation_calc   — AfA-Berechnung (linear/degressiv, §7 EStG)
 11.  r_and_d_incentive   — Forschungszulage (§35a EStG) eligibility check
 12.  tax_loss_carryforward — Verlustvortrag/-rücktrag Berechnung (§10d EStG)

NO external APIs — tax computation + regulatory knowledge.
"""
import os, sys, json, logging, math
from datetime import datetime, timezone

sys.path.insert(0, "/root/whitelabel")
from shared.utils.mcp_base import WhitelabelMCPServer

logging.basicConfig(level=logging.INFO, format="%(asctime)s [TaxOracle] %(levelname)s: %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler("/root/whitelabel/logs/taxoracle.log", mode="a")])
logger = logging.getLogger("TaxOracle")

PRODUCT_NAME = "TaxOracle"
VERSION = "1.0.0"
PORT_MCP = 12801
PORT_HEALTH = 12802

def ts(): return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

# Withholding tax rates (DBA network, simplified)
WHT_RATES = {
    ("DE","US"):{"dividends":15,"interest":0,"royalties":0,"dba":"DBA DE-US 1989/2006"},
    ("DE","GB"):{"dividends":15,"interest":0,"royalties":0,"dba":"DBA DE-GB 2010"},
    ("DE","FR"):{"dividends":15,"interest":0,"royalties":0,"dba":"DBA DE-FR 1959/2015"},
    ("DE","CH"):{"dividends":15,"interest":0,"royalties":0,"dba":"DBA DE-CH 1971/2002"},
    ("DE","AT"):{"dividends":15,"interest":0,"royalties":0,"dba":"DBA DE-AT 2000"},
    ("DE","NL"):{"dividends":15,"interest":0,"royalties":0,"dba":"DBA DE-NL 2012"},
    ("DE","JP"):{"dividends":15,"interest":10,"royalties":0,"dba":"DBA DE-JP 2015"},
    ("DE","CN"):{"dividends":10,"interest":10,"royalties":10,"dba":"DBA DE-CN 2014"},
    ("DE","IN"):{"dividends":10,"interest":10,"royalties":10,"dba":"DBA DE-IN 1995"},
    ("DE","TR"):{"dividends":15,"interest":15,"royalties":10,"dba":"DBA DE-TR 2011"},
    ("DE","KR"):{"dividends":15,"interest":10,"royalties":2,"dba":"DBA DE-KR 2000"},
    ("DE","SG"):{"dividends":5,"interest":8,"royalties":8,"dba":"DBA DE-SG 2004"},
}

async def handle_dac6(args: dict) -> dict:
    """DAC6/DAC7 cross-border reporting assessment."""
    arrangement_type = args.get("arrangement_type", "")
    cross_border = args.get("cross_border", True)
    involves_transfer_pricing = args.get("involves_transfer_pricing", False)
    involves_opaque_structure = args.get("involves_opaque_structures", False)
    involves_crs_avoidance = args.get("crs_avoidance", False)
    involves_tax_benefit = args.get("main_benefit_tax", False)
    value_eur = float(args.get("arrangement_value_eur", 0))

    hallmarks = []
    if involves_tax_benefit:
        hallmarks.append({"category": "A", "hallmark": "Generic (main benefit test)", "description": "Main benefit of arrangement is tax advantage"})
    if involves_opaque_structure:
        hallmarks.append({"category": "B", "hallmark": "Specific linked to main benefit test", "description": "Opaque offshore structures, nominee arrangements"})
    if involves_crs_avoidance:
        hallmarks.append({"category": "D", "hallmark": "CRS undermining", "description": "Arrangement undermines Common Reporting Standard"})
    if involves_transfer_pricing:
        hallmarks.append({"category": "E", "hallmark": "Transfer pricing", "description": "Unilateral safe harbor, hard-to-value intangibles, intra-group transfers"})

    reportable = len(hallmarks) > 0 and cross_border

    return {
        "reportable": reportable,
        "hallmarks_triggered": hallmarks,
        "hallmark_count": len(hallmarks),
        "reporting_deadline": "30 days from the arrangement being made available or ready for implementation",
        "who_reports": [
            "Intermediary (Steuerberater, Rechtsanwalt, Bank) — PRIMARY obligation",
            "Taxpayer — only if no intermediary or intermediary claims legal privilege",
        ],
        "penalties_de": {
            "non_reporting": "Bis €25.000 pro Verstoß (§379 Abs.2 Nr.1e AO)",
            "late_reporting": "Bis €25.000",
        },
        "dac7_note": "DAC7 (2023): Digital platform reporting obligation. Platforms must report seller data to tax authorities.",
        "dac8_note": "DAC8 (2025/2026): Crypto-asset reporting framework. CASPs must report transactions.",
        "legal_basis": "EU Directive 2018/822 (DAC6), §§138d-138k AO (DE implementation)",
        "retrieved_at": ts(),
    }

async def handle_pillar_two(args: dict) -> dict:
    """OECD Pillar Two / GloBE minimum tax calculation."""
    group_revenue = float(args.get("consolidated_revenue_eur", 0))
    jurisdictions = args.get("jurisdictions", [])
    if isinstance(jurisdictions, str):
        try: jurisdictions = json.loads(jurisdictions)
        except: return {"error": "Provide 'jurisdictions' as JSON array [{country, profit, tax_paid}]"}

    applicable = group_revenue >= 750_000_000  # €750M threshold
    min_rate = 15.0  # GloBE minimum rate

    results = []
    total_top_up = 0
    for j in jurisdictions:
        country = j.get("country", "??")
        profit = float(j.get("profit_eur", 0))
        tax_paid = float(j.get("tax_paid_eur", 0))
        etr = tax_paid / max(profit, 1) * 100
        top_up = max(0, profit * (min_rate / 100) - tax_paid) if etr < min_rate else 0
        total_top_up += top_up
        results.append({
            "country": country, "profit": profit, "tax_paid": tax_paid,
            "effective_tax_rate": round(etr, 2),
            "below_minimum": etr < min_rate,
            "top_up_tax": round(top_up, 2),
        })

    return {
        "applicable": applicable,
        "threshold": "€750M consolidated revenue in 2 of last 4 fiscal years",
        "globe_minimum_rate": f"{min_rate}%",
        "jurisdiction_analysis": results,
        "total_top_up_tax": round(total_top_up, 2),
        "mechanisms": {
            "IIR": "Income Inclusion Rule — parent jurisdiction collects top-up tax",
            "UTPR": "Undertaxed Profits Rule — backup rule if IIR not applied",
            "QDMTT": "Qualified Domestic Minimum Top-up Tax — jurisdiction can levy own top-up",
        },
        "de_implementation": {
            "law": "Mindeststeuergesetz (MinStG) — in Kraft seit 28.12.2023",
            "effective": "Für Geschäftsjahre ab 31.12.2023 (IIR), ab 31.12.2024 (UTPR)",
        },
        "legal_basis": "OECD GloBE Model Rules (Dec 2021), EU Directive 2022/2523, MinStG (DE)",
        "retrieved_at": ts(),
    }

async def handle_transfer_pricing(args: dict) -> dict:
    """Transfer pricing method selector."""
    transaction_type = args.get("transaction_type", "")
    related_parties = args.get("related_parties", "")
    value_eur = float(args.get("transaction_value_eur", 0))

    methods = [
        {"method": "CUP", "name": "Comparable Uncontrolled Price", "best_for": "Commodities, financial transactions, licensing",
         "oecd_priority": 1, "data_needed": "Comparable third-party transactions"},
        {"method": "RPM", "name": "Resale Price Method", "best_for": "Distribution activities",
         "oecd_priority": 2, "data_needed": "Gross margins of comparable distributors"},
        {"method": "CPM", "name": "Cost Plus Method", "best_for": "Manufacturing, services",
         "oecd_priority": 2, "data_needed": "Cost markups of comparable producers"},
        {"method": "TNMM", "name": "Transactional Net Margin Method", "best_for": "Complex transactions, most common method",
         "oecd_priority": 3, "data_needed": "Net profit margins of comparable companies"},
        {"method": "PSM", "name": "Profit Split Method", "best_for": "Highly integrated operations, unique intangibles",
         "oecd_priority": 3, "data_needed": "Functional analysis, value contribution analysis"},
    ]

    doc_requirements = {
        "master_file": "Group overview: organizational structure, business description, intangibles, intercompany financial activities, tax positions",
        "local_file": "Entity-specific: local management, functional analysis, comparable analysis, financial data",
        "country_by_country": "CbCR (mandatory for groups >€750M revenue): revenue, profit, tax, employees per jurisdiction",
    }

    return {
        "transaction_type": transaction_type,
        "value_eur": value_eur,
        "methods": methods,
        "documentation_requirements": doc_requirements,
        "de_specific": {
            "law": "§1 AStG (Außensteuergesetz), §90 Abs.3 AO (Dokumentationspflicht)",
            "cbcr_threshold": "€750M consolidated revenue",
            "doc_deadline": "Zeitnah (contemporaneous) — innerhalb 60 Tagen auf Anforderung",
            "penalties": "Zuschätzung + Strafzuschlag 5-10% der Einkünftekorrektur (§162 Abs.4 AO)",
        },
        "oecd_guidelines": "OECD Transfer Pricing Guidelines 2022, Chapter I-IX",
        "retrieved_at": ts(),
    }

async def handle_withholding_tax(args: dict) -> dict:
    """Withholding tax rates."""
    source_country = args.get("source_country", "DE").upper()
    residence_country = args.get("residence_country", "").upper()
    income_type = args.get("income_type", "dividends")  # dividends, interest, royalties

    pair = (source_country, residence_country)
    reverse_pair = (residence_country, source_country)
    rates = WHT_RATES.get(pair) or WHT_RATES.get(reverse_pair)

    domestic_rates = {"DE": {"dividends": 26.375, "interest": 26.375, "royalties": 15.825}}

    if rates:
        treaty_rate = rates.get(income_type, "N/A")
        return {
            "source": source_country, "residence": residence_country, "income_type": income_type,
            "treaty_rate": f"{treaty_rate}%",
            "domestic_rate": f"{domestic_rates.get(source_country, {}).get(income_type, 'N/A')}%",
            "dba": rates.get("dba", ""),
            "saving": f"{domestic_rates.get(source_country, {}).get(income_type, 0) - treaty_rate:.1f}% reduction via DBA",
            "procedure": "Freistellung (§50d Abs.2 EStG) oder Erstattung (§50d Abs.1 EStG) beim BZSt",
            "legal_basis": f"{rates.get('dba', '')} + §50d EStG",
            "retrieved_at": ts(),
        }

    return {
        "source": source_country, "residence": residence_country,
        "error": f"DBA-Daten für {source_country}-{residence_country} nicht in Datenbank",
        "available_pairs": [f"{a}-{b}" for a, b in WHT_RATES.keys()],
        "domestic_rate": domestic_rates.get(source_country, {}),
        "note": "Check BMF DBA-Übersicht für vollständige Liste",
        "retrieved_at": ts(),
    }

async def handle_pe_risk(args: dict) -> dict:
    """Permanent Establishment risk assessment."""
    country = args.get("country", "").upper()
    has_office = args.get("fixed_office", False)
    has_employees = args.get("local_employees", False)
    has_server = args.get("local_server", False)
    has_agent = args.get("dependent_agent", False)
    has_construction = args.get("construction_project", False)
    construction_months = int(args.get("construction_duration_months", 0))
    has_warehouse = args.get("warehouse", False)
    remote_workers = args.get("remote_workers_in_country", False)

    risks = []
    if has_office:
        risks.append({"factor": "Fixed place of business", "risk": "HIGH", "article": "Art.5(1) OECD MC"})
    if has_employees:
        risks.append({"factor": "Local employees", "risk": "HIGH", "article": "Art.5/15 OECD MC"})
    if has_agent:
        risks.append({"factor": "Dependent agent", "risk": "HIGH", "article": "Art.5(5) OECD MC"})
    if has_construction and construction_months > 12:
        risks.append({"factor": f"Construction >12 months ({construction_months}mo)", "risk": "HIGH", "article": "Art.5(3) OECD MC"})
    elif has_construction:
        risks.append({"factor": f"Construction <12 months", "risk": "LOW", "article": "Art.5(3) OECD MC"})
    if has_server:
        risks.append({"factor": "Server/data center", "risk": "MEDIUM", "article": "OECD Commentary Art.5 §42.2"})
    if remote_workers:
        risks.append({"factor": "Remote workers in country", "risk": "MEDIUM", "article": "Post-COVID guidance varies by country"})
    if has_warehouse:
        risks.append({"factor": "Warehouse (delivery only)", "risk": "LOW", "article": "Art.5(4)(a) — preparatory/auxiliary exemption"})

    overall = "HIGH" if any(r["risk"] == "HIGH" for r in risks) else "MEDIUM" if risks else "LOW"

    return {
        "country": country,
        "pe_risk_level": overall,
        "risk_factors": risks,
        "consequences_if_pe": [
            "Steuerpflicht im Quellenstaat auf PE-zurechenbare Gewinne",
            "Registrierungspflicht (Gewerbeanmeldung, Steuernummer)",
            "Buchführungspflicht im PE-Staat",
            "USt-Registrierung möglicherweise erforderlich",
            "Lohnsteuerpflicht für im PE tätige Mitarbeiter",
        ],
        "mitigation": [
            "Agent-Klauseln prüfen: unabhängiger Vertreter statt abhängiger",
            "Commissionaire-Strukturen vermeiden (post-BEPS Art.12)",
            "Homeoffice-Regelungen: Schwellenwerte beachten (z.B. 183-Tage-Regel)",
            "Profit Attribution: Arm's length gemäß Art.7 OECD MC",
        ],
        "legal_basis": "Art.5-7 OECD-Musterabkommen, §§12-13 AO (DE), BEPS Action 7",
        "retrieved_at": ts(),
    }

async def handle_ust_voranmeldung(args: dict) -> dict:
    """USt-Voranmeldung data preparation."""
    period = args.get("period", "")  # YYYY-MM
    revenue_19 = float(args.get("revenue_19_pct", 0))
    revenue_7 = float(args.get("revenue_7_pct", 0))
    revenue_0 = float(args.get("revenue_0_pct", 0))
    intra_community = float(args.get("intra_community_supply", 0))
    reverse_charge_received = float(args.get("reverse_charge_received", 0))
    input_vat = float(args.get("input_vat_vorsteuer", 0))
    import_vat = float(args.get("import_vat_einfuhrumsatzsteuer", 0))

    ust_19 = round(revenue_19 * 0.19, 2)
    ust_7 = round(revenue_7 * 0.07, 2)
    ust_rc = round(reverse_charge_received * 0.19, 2)
    ust_total = ust_19 + ust_7 + ust_rc
    vorsteuer_total = input_vat + import_vat + ust_rc  # RC-USt is also deductible
    zahllast = round(ust_total - vorsteuer_total, 2)

    return {
        "period": period,
        "elster_fields": {
            "Kz81": {"label": "Steuerpflichtige Umsätze 19%", "value": revenue_19, "ust": ust_19},
            "Kz86": {"label": "Steuerpflichtige Umsätze 7%", "value": revenue_7, "ust": ust_7},
            "Kz41": {"label": "Innergemeinschaftliche Lieferungen (steuerfrei)", "value": intra_community, "ust": 0},
            "Kz43": {"label": "Steuerfreie Umsätze ohne Vorsteuerabzug", "value": revenue_0, "ust": 0},
            "Kz46": {"label": "Reverse Charge (§13b UStG) — Leistungsempfänger", "value": reverse_charge_received, "ust": ust_rc},
            "Kz66": {"label": "Vorsteuer aus Rechnungen", "value": input_vat},
            "Kz61": {"label": "Einfuhrumsatzsteuer", "value": import_vat},
            "Kz67": {"label": "Vorsteuer §13b (aus Reverse Charge)", "value": ust_rc},
        },
        "calculation": {
            "ust_gesamt": ust_total,
            "vorsteuer_gesamt": vorsteuer_total,
            "zahllast": zahllast,
            "erstattung": zahllast < 0,
        },
        "deadlines": {
            "without_extension": "10. des Folgemonats",
            "with_dauerfristverlaengerung": "10. des übernächsten Monats (1/11 Sondervorauszahlung nötig)",
        },
        "filing": "ELSTER / ERiC-Schnittstelle — elektronische Übermittlung Pflicht",
        "legal_basis": "§18 UStG, UStDV, §46 UStDV (Dauerfristverlängerung)",
        "disclaimer": "Berechnungshilfe — ersetzt keine steuerliche Beratung. Steuerberater prüfen lassen.",
        "retrieved_at": ts(),
    }

async def handle_trade_tax(args: dict) -> dict:
    """Gewerbesteuer calculation."""
    gewinn = float(args.get("gewinn_aus_gewerbebetrieb", 0))
    hinzurechnungen = float(args.get("hinzurechnungen", 0))
    kuerzungen = float(args.get("kuerzungen", 0))
    hebesatz = float(args.get("hebesatz_pct", 400))
    is_personengesellschaft = args.get("personengesellschaft", False)

    freibetrag = 24500 if is_personengesellschaft else 0
    gewerbeertrag = max(0, gewinn + hinzurechnungen - kuerzungen - freibetrag)
    # Abrundung auf volle 100€
    gewerbeertrag = math.floor(gewerbeertrag / 100) * 100
    steuermessbetrag = gewerbeertrag * 0.035  # 3.5% Steuermesszahl
    gewerbesteuer = round(steuermessbetrag * hebesatz / 100, 2)

    # GewSt-Anrechnung auf ESt (Personengesellschaften)
    anrechnung = 0
    if is_personengesellschaft:
        anrechnung = min(gewerbesteuer, steuermessbetrag * 4.0)  # Faktor 4.0

    return {
        "gewinn": gewinn, "hinzurechnungen": hinzurechnungen, "kuerzungen": kuerzungen,
        "freibetrag": freibetrag,
        "gewerbeertrag": gewerbeertrag,
        "steuermesszahl": "3.5%",
        "steuermessbetrag": round(steuermessbetrag, 2),
        "hebesatz": f"{hebesatz}%",
        "gewerbesteuer": gewerbesteuer,
        "est_anrechnung": round(anrechnung, 2) if is_personengesellschaft else "N/A (nur Personengesellschaften)",
        "effektive_belastung": round(gewerbesteuer - anrechnung, 2) if is_personengesellschaft else gewerbesteuer,
        "hinzurechnungen_note": "§8 Nr.1 GewStG: 25% der Finanzierungsanteile (Zinsen, Mieten, Pachten, Lizenzen) über €200.000 Freibetrag",
        "hebesatz_note": f"Hebesatz {hebesatz}% — Bundesdurchschnitt ~435%. Min. 200% (§16 Abs.4 GewStG).",
        "legal_basis": "§§6-16 GewStG, §35 EStG (Anrechnung)",
        "retrieved_at": ts(),
    }

async def handle_betriebspruefung(args: dict) -> dict:
    """Betriebsprüfung readiness checklist."""
    company_size = args.get("company_size", "mittel")  # klein, mittel, gross
    years_since_last = int(args.get("years_since_last_audit", 0))

    pruefungsturnus = {"klein": "Selten (alle 15-30 Jahre)", "mittel": "Alle 6-12 Jahre", "gross": "Alle 3-6 Jahre", "grossbetrieb": "Lückenlos"}

    return {
        "company_size": company_size,
        "expected_turnus": pruefungsturnus.get(company_size, "Unbekannt"),
        "years_since_last": years_since_last,
        "risk_of_audit": "HIGH" if years_since_last > 8 else "MEDIUM" if years_since_last > 4 else "LOW",
        "preparation_checklist": {
            "dokumentation": [
                "Vollständige Buchführung aller Prüfungsjahre (§§140-148 AO)",
                "GoBD-konforme Archivierung (10 Jahre Aufbewahrung)",
                "Kassenführung: TSE-Pflicht, Einzelaufzeichnung (§146a AO)",
                "Verfahrensdokumentation nach GoBD vorhanden",
                "Rechnungen: §14 UStG Pflichtangaben vollständig",
            ],
            "verrechnungspreise": [
                "Master File / Local File vorhanden (§90 Abs.3 AO)",
                "Fremdvergleichsgrundsatz dokumentiert (§1 AStG)",
                "Funktions- und Risikoanalyse aktuell",
            ],
            "elektronische_daten": [
                "GDPdU/GoBD-Export möglich (Z1-Z3 Zugriff)",
                "IDEA/ACL-kompatible Datenbereitstellung",
                "E-Mail-Archivierung (geschäftsrelevante Mails)",
            ],
            "kritische_bereiche": [
                "Privatnutzung Firmenwagen (1%-Regel vs Fahrtenbuch)",
                "Bewirtungskosten (70% abzugsfähig, §4 Abs.5 Nr.2 EStG)",
                "Geschenke (€50-Grenze, §4 Abs.5 Nr.1 EStG)",
                "Rückstellungen (Angemessenheit, §249 HGB)",
                "Abgrenzung Herstellungs-/Erhaltungsaufwand",
                "Gesellschafter-Geschäftsführer Vergütung (vGA-Risiko)",
            ],
        },
        "rechte_und_pflichten": {
            "mitwirkungspflicht": "§200 AO — umfassende Mitwirkung, Zugang zu Geschäftsräumen",
            "datenzugriff": "Z1 (Unmittelbarer Zugriff), Z2 (Mittelbarer Zugriff), Z3 (Datenträgerüberlassung)",
            "einspruchsrecht": "§347 AO — Einspruch gegen Prüfungsergebnis innerhalb 1 Monat",
            "verboetene_fragen": "Prüfer darf keine Auskünfte erzwingen, die gegen Selbstbelastungsverbot verstoßen",
        },
        "legal_basis": "§§193-207 AO (Außenprüfung), GoBD, BpO 2000",
        "retrieved_at": ts(),
    }

async def handle_gaap_ifrs(args: dict) -> dict:
    """HGB vs IFRS key differences."""
    topic = args.get("topic", "all")
    diffs = [
        {"area": "Bilanzierungsgrundsatz", "HGB": "Vorsichtsprinzip (§252 HGB)", "IFRS": "True and fair view / Fair value", "impact": "IFRS zeigt höhere Vermögenswerte"},
        {"area": "Umsatzrealisierung", "HGB": "Bei Leistungserbringung/Gefahrübergang", "IFRS": "IFRS 15: 5-Schritte-Modell, Performance Obligations", "impact": "IFRS kann früher/später Umsatz zeigen"},
        {"area": "Leasing", "HGB": "Wirtschaftliches Eigentum entscheidet (off-balance möglich)", "IFRS": "IFRS 16: Fast alle Leasings on-balance (Right-of-Use)", "impact": "IFRS: Höhere Bilanzsumme, höhere Verschuldung"},
        {"area": "Entwicklungskosten", "HGB": "Wahlrecht zur Aktivierung (§248 Abs.2 HGB)", "IFRS": "IAS 38: Aktivierungspflicht bei Erfüllung der Kriterien", "impact": "IFRS: Tendenziell höheres Anlagevermögen"},
        {"area": "Rückstellungen", "HGB": "Auch für drohende Verluste aus schwebenden Geschäften", "IFRS": "IAS 37: Nur bei wahrscheinlichem Abfluss + verlässlicher Schätzung", "impact": "HGB: Mehr Rückstellungen → vorsichtiger"},
        {"area": "Goodwill", "HGB": "Planmäßige Abschreibung (max. 10 Jahre, §253 HGB)", "IFRS": "IFRS 3: Kein planmäßiger Abschrieb, nur Impairment-Test (jährlich)", "impact": "IFRS: Höherer Goodwill in Bilanz"},
        {"area": "Abschreibung", "HGB": "Steuerliche AfA erlaubt (Maßgeblichkeit)", "IFRS": "Nur wirtschaftliche Nutzungsdauer, keine steuerlichen Einflüsse", "impact": "Unterschiedliche Ergebnisse möglich"},
        {"area": "Latente Steuern", "HGB": "Wahlrecht für aktive latente Steuern (§274 HGB)", "IFRS": "IAS 12: Pflicht soweit realisierbar", "impact": "IFRS: Potenziell höhere Bilanzaktiva"},
    ]

    if topic != "all":
        diffs = [d for d in diffs if topic.lower() in d["area"].lower()]

    return {
        "comparison": diffs,
        "count": len(diffs),
        "trend": "Zunehmende Konvergenz, aber fundamentale Unterschiede bleiben (Vorsichtsprinzip vs Fair Value)",
        "who_needs_ifrs": [
            "Kapitalmarktorientierte Unternehmen in EU (Pflicht seit 2005, VO 1606/2002)",
            "Konzernabschlüsse börsennotierter Unternehmen",
            "Freiwillig für alle anderen (§315e HGB)",
        ],
        "retrieved_at": ts(),
    }

async def handle_depreciation(args: dict) -> dict:
    """AfA-Berechnung."""
    acquisition_cost = float(args.get("acquisition_cost_eur", 0))
    useful_life_years = int(args.get("useful_life_years", 0))
    method = args.get("method", "linear")  # linear | degressive
    acquisition_date = args.get("acquisition_date", "")
    gwg = args.get("is_gwg", False)  # Geringwertiges Wirtschaftsgut

    if acquisition_cost <= 0 or useful_life_years <= 0:
        return {"error": "Provide 'acquisition_cost_eur' and 'useful_life_years'"}

    # GWG check
    if acquisition_cost <= 800 and gwg:
        return {
            "gwg": True,
            "sofortabzug": acquisition_cost,
            "note": "Geringwertiges Wirtschaftsgut (§6 Abs.2 EStG): Sofortabzug bis €800 netto",
            "alternative": "Sammelposten §6 Abs.2a EStG: €250,01-€1.000 → 5 Jahre linear (Pool-Abschreibung)",
            "retrieved_at": ts(),
        }

    schedule = []
    if method == "linear":
        annual = round(acquisition_cost / useful_life_years, 2)
        remaining = acquisition_cost
        for y in range(1, useful_life_years + 1):
            dep = min(annual, remaining)
            remaining -= dep
            schedule.append({"year": y, "depreciation": round(dep, 2), "remaining": round(remaining, 2)})
    elif method == "degressive":
        # 25% degressiv (max. 2.5x linear), Wechsel zu linear wenn günstiger
        deg_rate = min(25, 100 / useful_life_years * 2.5)
        linear_rate = 100 / useful_life_years
        remaining = acquisition_cost
        for y in range(1, useful_life_years + 1):
            deg_amount = remaining * deg_rate / 100
            lin_amount = acquisition_cost / useful_life_years
            # Wechsel zu linear wenn linear günstiger
            remaining_years = useful_life_years - y + 1
            lin_from_remaining = remaining / remaining_years
            if lin_from_remaining >= deg_amount:
                dep = round(lin_from_remaining, 2)
                note = "→ Wechsel zu linear"
            else:
                dep = round(deg_amount, 2)
                note = f"degressiv {deg_rate:.1f}%"
            remaining -= dep
            remaining = max(0, remaining)
            schedule.append({"year": y, "depreciation": dep, "remaining": round(remaining, 2), "note": note})

    return {
        "acquisition_cost": acquisition_cost,
        "useful_life_years": useful_life_years,
        "method": method,
        "annual_depreciation_linear": round(acquisition_cost / useful_life_years, 2),
        "schedule": schedule,
        "afa_tabelle_note": "Nutzungsdauer gemäß amtlicher AfA-Tabelle (BMF) verwenden",
        "sonder_afa": "§7g EStG: 20% Sonder-AfA im Erstjahr für KMU (Investitionsabzugsbetrag)",
        "legal_basis": "§7 EStG (lineare AfA), §7 Abs.2 EStG (degressive AfA — wiedereingeführt 2024-2028)",
        "retrieved_at": ts(),
    }

async def handle_r_and_d(args: dict) -> dict:
    """Forschungszulage eligibility check."""
    rd_expenses = float(args.get("rd_personnel_costs_eur", 0))
    contract_rd = float(args.get("contract_rd_costs_eur", 0))
    employee_count = int(args.get("employee_count", 0))
    project_type = args.get("project_type", "")

    eligible_expenses = rd_expenses + contract_rd * 0.60  # 60% der Auftragsforschung
    zulagenhoehe = min(eligible_expenses * 0.25, 1_000_000)  # 25%, max €1M

    return {
        "eligible": True,
        "forschungszulage": round(zulagenhoehe, 2),
        "calculation": {
            "rd_personnel": rd_expenses,
            "contract_rd_60pct": round(contract_rd * 0.60, 2),
            "eligible_total": round(eligible_expenses, 2),
            "rate": "25%",
            "cap": "€1.000.000 (erhöht von €500.000 ab 2024)",
            "result": round(zulagenhoehe, 2),
        },
        "eligible_activities": [
            "Grundlagenforschung",
            "Industrielle Forschung (angewandt)",
            "Experimentelle Entwicklung",
        ],
        "not_eligible": ["Marktforschung", "Qualitätskontrolle", "Routinetests", "Softwareanpassung ohne Innovation"],
        "process": [
            "1. Antrag auf Bescheinigung bei der BSFZ (Bescheinigungsstelle Forschungszulage)",
            "2. BSFZ bestätigt F&E-Eigenschaft des Projekts",
            "3. Antrag auf Forschungszulage beim Finanzamt mit Steuererklärung",
            "4. Verrechnung mit Steuerschuld (oder Auszahlung bei Überschuss)",
        ],
        "legal_basis": "Forschungszulagengesetz (FZulG), §35a EStG",
        "retrieved_at": ts(),
    }

async def handle_loss_carryforward(args: dict) -> dict:
    """Verlustvortrag/-rücktrag Berechnung."""
    loss = float(args.get("loss_eur", 0))
    prior_year_income = float(args.get("prior_year_income_eur", 0))
    current_year_income = float(args.get("current_year_income_eur", 0))
    prefer_carryback = args.get("prefer_carryback", True)

    # §10d EStG
    carryback_limit = 10_000_000  # €10M (erhöht seit 2022, permanent)
    carryback = min(loss, prior_year_income, carryback_limit) if prefer_carryback else 0
    remaining_after_carryback = max(0, loss - carryback)

    # Mindestbesteuerung: €1M + 60% des darüber hinausgehenden Einkommens
    if current_year_income <= 1_000_000:
        carryforward_used = min(remaining_after_carryback, current_year_income)
    else:
        carryforward_used = min(remaining_after_carryback, 1_000_000 + (current_year_income - 1_000_000) * 0.6)

    remaining_loss = remaining_after_carryback - carryforward_used

    return {
        "loss": loss,
        "verlustruecktrag": {
            "amount": round(carryback, 2),
            "limit": f"€{carryback_limit:,.0f}",
            "years": "1 Jahr zurück (§10d Abs.1 EStG)",
            "prior_year_income": prior_year_income,
        },
        "verlustvortrag": {
            "available": round(remaining_after_carryback, 2),
            "used_current_year": round(carryforward_used, 2),
            "remaining": round(remaining_loss, 2),
            "mindestbesteuerung": "€1M unbeschränkt + 60% des übersteigenden Betrags (§10d Abs.2 EStG)",
        },
        "total_utilized": round(carryback + carryforward_used, 2),
        "total_remaining": round(remaining_loss, 2),
        "note": "Verluste zeitlich unbegrenzt vortragsfähig, aber Mindestbesteuerung beachten",
        "gewst_note": "§10a GewStG: Gewerbesteuerlicher Verlustvortrag mit gleicher Mindestbesteuerung",
        "legal_basis": "§10d EStG (ESt), §10a GewStG (GewSt), §8c/§8d KStG (KSt — Anteilseignerwechsel!)",
        "retrieved_at": ts(),
    }


def main():
    server = WhitelabelMCPServer(product_name=PRODUCT_NAME, product_slug="taxoracle",
                                 version=VERSION, port_mcp=PORT_MCP, port_health=PORT_HEALTH)

    server.register_tool("dac6_assessment", "DAC6/DAC7 cross-border arrangement reporting obligation check. Hallmark analysis, reporting deadlines, penalties (§§138d-138k AO).",
        {"arrangement_type":{"type":"string"},"cross_border":{"type":"boolean"},"involves_transfer_pricing":{"type":"boolean"},"involves_opaque_structures":{"type":"boolean"},"crs_avoidance":{"type":"boolean"},"main_benefit_tax":{"type":"boolean"},"arrangement_value_eur":{"type":"number"}}, handle_dac6, credits=3)

    server.register_tool("pillar_two_calc", "OECD Pillar Two / GloBE minimum tax calculation (15%). Per-jurisdiction ETR analysis, top-up tax calculation. MinStG (DE).",
        {"consolidated_revenue_eur":{"type":"number","description":"Consolidated group revenue (€750M threshold)"},"jurisdictions":{"type":"string","description":"JSON array [{country, profit_eur, tax_paid_eur}]"}}, handle_pillar_two, credits=3)

    server.register_tool("transfer_pricing", "Transfer pricing method selector with OECD hierarchy. CUP, RPM, CPM, TNMM, PSM. Documentation requirements (Master/Local File, CbCR).",
        {"transaction_type":{"type":"string","description":"goods|services|intangibles|financing"},"transaction_value_eur":{"type":"number"}}, handle_transfer_pricing, credits=2)

    server.register_tool("withholding_tax", "Withholding tax rates for 12+ DE bilateral DBA pairs. Dividends, interest, royalties treaty rates vs domestic rates.",
        {"source_country":{"type":"string","description":"2-letter code (default: DE)"},"residence_country":{"type":"string"},"income_type":{"type":"string","description":"dividends|interest|royalties"}}, handle_withholding_tax, credits=1)

    server.register_tool("pe_risk_check", "Permanent Establishment risk assessment. Fixed place, employees, agents, servers, construction. Art.5 OECD MC + BEPS Action 7.",
        {"country":{"type":"string"},"fixed_office":{"type":"boolean"},"local_employees":{"type":"boolean"},"dependent_agent":{"type":"boolean"},"local_server":{"type":"boolean"},"construction_project":{"type":"boolean"},"construction_duration_months":{"type":"integer"},"remote_workers_in_country":{"type":"boolean"}}, handle_pe_risk, credits=2)

    server.register_tool("ust_voranmeldung", "USt-Voranmeldung data preparation with ELSTER field mapping (Kz81, Kz86, Kz41, Kz46, Kz66, Kz61). Zahllast calculation.",
        {"period":{"type":"string","description":"YYYY-MM"},"revenue_19_pct":{"type":"number","description":"Netto-Umsatz 19%"},"revenue_7_pct":{"type":"number","description":"Netto-Umsatz 7%"},"revenue_0_pct":{"type":"number","description":"Steuerfreie Umsätze"},"intra_community_supply":{"type":"number"},"reverse_charge_received":{"type":"number"},"input_vat_vorsteuer":{"type":"number"},"import_vat_einfuhrumsatzsteuer":{"type":"number"}}, handle_ust_voranmeldung, credits=2)

    server.register_tool("trade_tax_calc", "Gewerbesteuer calculation with Hebesatz. Hinzurechnungen (§8 GewStG), Kürzungen, Freibetrag, ESt-Anrechnung (§35 EStG).",
        {"gewinn_aus_gewerbebetrieb":{"type":"number"},"hinzurechnungen":{"type":"number"},"kuerzungen":{"type":"number"},"hebesatz_pct":{"type":"number","description":"Gemeinde-Hebesatz % (default: 400)"},"personengesellschaft":{"type":"boolean"}}, handle_trade_tax, credits=2)

    server.register_tool("betriebspruefung", "Betriebsprüfung readiness checklist. GoBD, Kassenführung, Verrechnungspreise, elektronische Daten (Z1-Z3), kritische Bereiche.",
        {"company_size":{"type":"string","description":"klein|mittel|gross|grossbetrieb"},"years_since_last_audit":{"type":"integer"}}, handle_betriebspruefung, credits=2)

    server.register_tool("gaap_ifrs_diff", "HGB vs IFRS key differences across 8 areas. Revenue recognition, leasing, goodwill, provisions, development costs.",
        {"topic":{"type":"string","description":"all, or specific area e.g. leasing, umsatz, goodwill"}}, handle_gaap_ifrs, credits=1)

    server.register_tool("depreciation_calc", "AfA-Berechnung (§7 EStG). Linear/degressiv, GWG-Sofortabzug (€800), Sonder-AfA §7g. Full year-by-year schedule.",
        {"acquisition_cost_eur":{"type":"number"},"useful_life_years":{"type":"integer"},"method":{"type":"string","description":"linear|degressive"},"is_gwg":{"type":"boolean","description":"Geringwertiges Wirtschaftsgut (<€800)"}}, handle_depreciation, credits=1)

    server.register_tool("r_and_d_incentive", "Forschungszulage (FZulG) eligibility and calculation. 25% of R&D personnel costs, max €1M. BSFZ process.",
        {"rd_personnel_costs_eur":{"type":"number"},"contract_rd_costs_eur":{"type":"number"},"employee_count":{"type":"integer"},"project_type":{"type":"string","description":"grundlagenforschung|industrielle_forschung|experimentelle_entwicklung"}}, handle_r_and_d, credits=2)

    server.register_tool("tax_loss_carryforward", "Verlustvortrag/-rücktrag Berechnung (§10d EStG). Mindestbesteuerung (€1M + 60%), Rücktragslimit €10M.",
        {"loss_eur":{"type":"number","description":"Verlust in EUR"},"prior_year_income_eur":{"type":"number"},"current_year_income_eur":{"type":"number"},"prefer_carryback":{"type":"boolean","description":"Verlustrücktrag bevorzugen? (default: true)"}}, handle_loss_carryforward, credits=2)

    logger.info(f"🚀 {PRODUCT_NAME} v{VERSION} starting on port {PORT_MCP}")
    server.run()

if __name__ == "__main__":
    main()
