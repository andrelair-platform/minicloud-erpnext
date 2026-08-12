"""CRM (Compte Rendu Métier) XML response fixtures for DSN submitter tests."""

# Happy path — accepted, no errors
ACCEPTE = """<?xml version="1.0" encoding="UTF-8"?>
<crm:compteRenduMetier xmlns:crm="urn:net-entreprises:crm:1.0" version="1.0">
  <crm:identifiantEnvoi>0B48A581</crm:identifiantEnvoi>
  <crm:dateTraitement>2026-08-12T09:22:08Z</crm:dateTraitement>
  <crm:etatTraitement>ACCEPTE</crm:etatTraitement>
  <crm:codeRetour>00</crm:codeRetour>
  <crm:libelleRetour>Traitement sans erreur — Fichier accepté</crm:libelleRetour>
  <crm:statistiques>
    <crm:nombreIndividus>1</crm:nombreIndividus>
  </crm:statistiques>
</crm:compteRenduMetier>"""

# Rejected — format error
REJETE = """<?xml version="1.0" encoding="UTF-8"?>
<crm:compteRenduMetier xmlns:crm="urn:net-entreprises:crm:1.0" version="1.0">
  <crm:etatTraitement>REJETE</crm:etatTraitement>
  <crm:codeRetour>10</crm:codeRetour>
  <crm:libelleRetour>Fichier rejeté — format invalide</crm:libelleRetour>
</crm:compteRenduMetier>"""

# Accepted state but non-zero code (accepted with reservation)
ACCEPTE_NONZERO_CODE = """<?xml version="1.0" encoding="UTF-8"?>
<crm:compteRenduMetier xmlns:crm="urn:net-entreprises:crm:1.0" version="1.0">
  <crm:etatTraitement>ACCEPTE</crm:etatTraitement>
  <crm:codeRetour>01</crm:codeRetour>
  <crm:libelleRetour>Accepté avec réserve</crm:libelleRetour>
</crm:compteRenduMetier>"""

# SOAP fault (infrastructure error, non-XML-CRM wrapper)
SOAP_FAULT = """<?xml version="1.0"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <soap:Fault>
      <faultcode>soap:Server</faultcode>
      <faultstring>Internal Server Error</faultstring>
    </soap:Fault>
  </soap:Body>
</soap:Envelope>"""

# Completely empty body
EMPTY = ""

# Plain text (non-XML) success-like response — no fault keywords
PLAIN_OK = "Fichier recu avec succes."

# Regression fixture: the original bug — "Traitement sans erreur" contains "erreur"
# The naive keyword check would return False here. The XML parser returns True.
TRAITEMENT_SANS_ERREUR = ACCEPTE  # same as ACCEPTE — the libellé contains "erreur"
