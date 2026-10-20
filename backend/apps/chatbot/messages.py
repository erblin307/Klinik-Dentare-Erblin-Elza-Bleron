"""
Fixed chatbot texts in Albanian, English and German.

Everything that states a booking fact (times, dentists, references) is
produced from these templates, never by the language model, so it cannot be
altered or invented. Clinic details are always filled in from the database.
"""

from apps.appointments.booking import BookingErrorCode

WEEKDAYS = {
    "sq": ["e hënë", "e martë", "e mërkurë", "e enjte", "e premte", "e shtunë", "e diel"],
    "en": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
    "de": ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"],
}

_DATETIME = {
    "sq": "{weekday}, {date}, ora {time}",
    "en": "{weekday} {date} at {time}",
    "de": "{weekday}, {date}, {time} Uhr",
}

FIELD_LABELS = {
    "sq": {"first_name": "emri", "last_name": "mbiemri", "phone": "numri i telefonit"},
    "en": {"first_name": "first name", "last_name": "last name", "phone": "phone number"},
    "de": {"first_name": "Vorname", "last_name": "Nachname", "phone": "Telefonnummer"},
}

_AND = {"sq": "dhe", "en": "and", "de": "und"}

TEMPLATES = {
    "greeting": {
        "sq": "Përshëndetje! Jam asistenti virtual i {clinic}. Mund t'ju ndihmoj me "
        "informacione për shërbimet, çmimet dhe oraret, ose të rezervoni, anuloni apo "
        "ndryshoni një termin.",
        "en": "Hello! I am the virtual assistant of {clinic}. I can help with information "
        "about our services, prices and hours, or book, cancel or reschedule an appointment.",
        "de": "Guten Tag! Ich bin der virtuelle Assistent von {clinic}. Ich helfe Ihnen gern "
        "mit Informationen zu Leistungen, Preisen und Zeiten oder beim Buchen, Absagen und "
        "Verschieben eines Termins.",
    },
    "unavailable": {
        "sq": "Më vjen keq, asistenti nuk është i disponueshëm për momentin. {contact}",
        "en": "Sorry, the assistant is not available at the moment. {contact}",
        "de": "Der Assistent ist momentan leider nicht verfügbar. {contact}",
    },
    "medical": {
        "sq": "Nuk mund të jap diagnoza apo këshilla mjekësore. Ju rekomandoj një konsultë "
        "me një nga dentistët tanë – mund ta rezervoj për ju. Në rast urgjence: {contact}",
        "en": "I cannot give diagnoses or medical advice. I recommend a consultation with one "
        "of our dentists – I can book it for you. In an emergency: {contact}",
        "de": "Ich kann keine Diagnosen oder medizinischen Ratschläge geben. Ich empfehle eine "
        "Untersuchung bei einem unserer Zahnärzte – ich kann sie für Sie buchen. Im Notfall: "
        "{contact}",
    },
    "ask_service": {
        "sq": "Për cilin shërbim dëshironi termin? Ofrojmë: {services}.",
        "en": "Which service would you like to book? We offer: {services}.",
        "de": "Für welche Leistung möchten Sie einen Termin? Wir bieten: {services}.",
    },
    "no_services": {
        "sq": "Rezervimi online nuk është i mundur për momentin. {contact}",
        "en": "Online booking is not available at the moment. {contact}",
        "de": "Online-Buchungen sind derzeit nicht möglich. {contact}",
    },
    "no_slots": {
        "sq": "Nuk gjeta termin të lirë për {service} në datat e kërkuara. Dëshironi të "
        "provoni një ditë tjetër?",
        "en": "I could not find a free appointment for {service} on the requested dates. "
        "Would you like to try another day?",
        "de": "Für {service} habe ich zu den gewünschten Daten keinen freien Termin gefunden. "
        "Möchten Sie einen anderen Tag versuchen?",
    },
    "offer_slots": {
        "sq": "Terminet e lira për {service}:\n{options}\nJu lutemi shkruani numrin e "
        "terminit që preferoni.",
        "en": "Available appointments for {service}:\n{options}\nPlease reply with the number "
        "of the time you prefer.",
        "de": "Freie Termine für {service}:\n{options}\nBitte antworten Sie mit der Nummer "
        "des gewünschten Termins.",
    },
    "option_line": {
        "sq": "{number}. {when} – {dentist}",
        "en": "{number}. {when} – {dentist}",
        "de": "{number}. {when} – {dentist}",
    },
    "choose_from_list": {
        "sq": "Ju lutemi zgjidhni një nga numrat e listës:\n{options}",
        "en": "Please choose one of the numbers from the list:\n{options}",
        "de": "Bitte wählen Sie eine Nummer aus der Liste:\n{options}",
    },
    "ask_details": {
        "sq": "Për të rezervuar terminin ({when}), më duhen këto të dhëna: {fields}.",
        "en": "To book the appointment ({when}), I still need the following details: {fields}.",
        "de": "Um den Termin ({when}) zu buchen, benötige ich noch folgende Angaben: {fields}.",
    },
    "invalid_phone": {
        "sq": "Numri i telefonit nuk duket i saktë. Ju lutemi shkruajeni me prefiksin e "
        "shtetit (duke filluar me +).",
        "en": "That phone number does not look right. Please include the country code "
        "(starting with +).",
        "de": "Die Telefonnummer scheint nicht korrekt zu sein. Bitte mit Ländervorwahl "
        "angeben (beginnend mit +).",
    },
    "confirm_booking": {
        "sq": "Ju lutemi konfirmoni: {service} me {dentist}, {when}, për {name} ({phone}). "
        "Shkruani \"po\" për ta rezervuar ose \"jo\" për ta anuluar.",
        "en": "Please confirm: {service} with {dentist}, {when}, for {name} ({phone}). "
        "Reply \"yes\" to book or \"no\" to cancel.",
        "de": "Bitte bestätigen Sie: {service} bei {dentist}, {when}, für {name} ({phone}). "
        "Antworten Sie mit \"ja\" zum Buchen oder \"nein\" zum Abbrechen.",
    },
    "booked": {
        "sq": "Termini juaj u konfirmua: {service} me {dentist}, {when}. Kodi i rezervimit: "
        "{reference}. Ruajeni këtë kod – ju duhet për ta anuluar ose ndryshuar terminin.",
        "en": "Your appointment is confirmed: {service} with {dentist}, {when}. Your booking "
        "reference is {reference}. Please keep it – you need it to cancel or reschedule.",
        "de": "Ihr Termin ist bestätigt: {service} bei {dentist}, {when}. Ihre Buchungsnummer "
        "lautet {reference}. Bitte bewahren Sie sie auf – Sie benötigen sie zum Absagen oder "
        "Verschieben.",
    },
    "ask_reference": {
        "sq": "Ju lutemi më dërgoni kodin e rezervimit (8 karaktere, p.sh. AB3D-EF7H).",
        "en": "Please send me your booking reference (8 characters, e.g. AB3D-EF7H).",
        "de": "Bitte senden Sie mir Ihre Buchungsnummer (8 Zeichen, z. B. AB3D-EF7H).",
    },
    "reference_not_found": {
        "sq": "Nuk gjeta asnjë termin me këtë kod. Ju lutemi kontrollojeni dhe provoni përsëri.",
        "en": "I could not find an appointment with that reference. Please check it and try "
        "again.",
        "de": "Zu dieser Buchungsnummer habe ich keinen Termin gefunden. Bitte prüfen Sie sie "
        "und versuchen Sie es erneut.",
    },
    "too_many_attempts": {
        "sq": "Shumë përpjekje të pasuksesshme. {contact}",
        "en": "Too many unsuccessful attempts. {contact}",
        "de": "Zu viele erfolglose Versuche. {contact}",
    },
    "not_changeable": {
        "sq": "Ky termin nuk mund të ndryshohet më online. {contact}",
        "en": "This appointment can no longer be changed online. {contact}",
        "de": "Dieser Termin kann online nicht mehr geändert werden. {contact}",
    },
    "confirm_cancel": {
        "sq": "Dëshironi të anuloni {service} me {dentist}, {when}? Shkruani \"po\" për ta "
        "anuluar ose \"jo\" për ta mbajtur.",
        "en": "Do you want to cancel {service} with {dentist}, {when}? Reply \"yes\" to cancel "
        "it or \"no\" to keep it.",
        "de": "Möchten Sie {service} bei {dentist}, {when}, absagen? Antworten Sie mit \"ja\" "
        "zum Absagen oder \"nein\", um ihn zu behalten.",
    },
    "cancelled": {
        "sq": "Termini juaj ({when}) u anulua.",
        "en": "Your appointment on {when} has been cancelled.",
        "de": "Ihr Termin am {when} wurde abgesagt.",
    },
    "current_appointment": {
        "sq": "Termini juaj aktual: {service} me {dentist}, {when}.",
        "en": "Your current appointment: {service} with {dentist}, {when}.",
        "de": "Ihr aktueller Termin: {service} bei {dentist}, {when}.",
    },
    "confirm_reschedule": {
        "sq": "Ta zhvendos {service} nga {old} në {new} me {dentist}? Shkruani \"po\" për ta "
        "konfirmuar ose \"jo\" për ta lënë siç është.",
        "en": "Move {service} from {old} to {new} with {dentist}? Reply \"yes\" to confirm or "
        "\"no\" to keep it as it is.",
        "de": "Soll {service} von {old} auf {new} bei {dentist} verschoben werden? Antworten "
        "Sie mit \"ja\" zum Bestätigen oder \"nein\", um ihn unverändert zu lassen.",
    },
    "rescheduled": {
        "sq": "U krye! Termini juaj tani është {when} me {dentist}. Kodi i rezervimit mbetet "
        "{reference}.",
        "en": "Done! Your appointment is now on {when} with {dentist}. Your booking reference "
        "stays {reference}.",
        "de": "Erledigt! Ihr Termin ist jetzt am {when} bei {dentist}. Ihre Buchungsnummer "
        "bleibt {reference}.",
    },
    "declined": {
        "sq": "Në rregull, nuk bëra asnjë ndryshim.",
        "en": "All right, I have not made any changes.",
        "de": "In Ordnung, ich habe nichts geändert.",
    },
    "confirm_hint": {
        "sq": "Ju lutemi shkruani \"po\" për të konfirmuar ose \"jo\" për ta anuluar.",
        "en": "Please reply \"yes\" to confirm or \"no\" to cancel.",
        "de": "Bitte antworten Sie mit \"ja\" zum Bestätigen oder \"nein\" zum Abbrechen.",
    },
    "nothing_to_confirm": {
        "sq": "Nuk ka asgjë për të konfirmuar.",
        "en": "There is nothing to confirm.",
        "de": "Es gibt nichts zu bestätigen.",
    },
    "failed": {
        "sq": "Më vjen keq, kjo nuk është e mundur: {reason}",
        "en": "Sorry, that is not possible: {reason}",
        "de": "Das ist leider nicht möglich: {reason}",
    },
    "contact_phone": {
        "sq": "Ju lutemi kontaktoni klinikën në {phone}.",
        "en": "Please contact the clinic at {phone}.",
        "de": "Bitte kontaktieren Sie die Praxis unter {phone}.",
    },
    "contact_email": {
        "sq": "Ju lutemi kontaktoni klinikën në {email}.",
        "en": "Please contact the clinic at {email}.",
        "de": "Bitte kontaktieren Sie die Praxis unter {email}.",
    },
    "contact_none": {
        "sq": "Ju lutemi kontaktoni klinikën drejtpërdrejt.",
        "en": "Please contact the clinic directly.",
        "de": "Bitte wenden Sie sich direkt an die Praxis.",
    },
}

REASONS = {
    BookingErrorCode.SLOT_TAKEN: {
        "sq": "ky orar sapo u zu.",
        "en": "this time has just been taken.",
        "de": "dieser Termin wurde gerade vergeben.",
    },
    BookingErrorCode.PATIENT_BUSY: {
        "sq": "keni tashmë një termin në këtë orë.",
        "en": "you already have an appointment at this time.",
        "de": "Sie haben zu dieser Zeit bereits einen Termin.",
    },
    BookingErrorCode.OUTSIDE_WORKING_HOURS: {
        "sq": "ky orar është jashtë orarit të punës.",
        "en": "this time is outside working hours.",
        "de": "diese Zeit liegt außerhalb der Sprechzeiten.",
    },
    BookingErrorCode.TIME_OFF: {
        "sq": "dentisti nuk është i disponueshëm në këtë kohë.",
        "en": "the dentist is not available at this time.",
        "de": "der Zahnarzt ist zu dieser Zeit nicht verfügbar.",
    },
    BookingErrorCode.IN_THE_PAST: {
        "sq": "ky orar ka kaluar.",
        "en": "this time is in the past.",
        "de": "dieser Zeitpunkt liegt in der Vergangenheit.",
    },
}
_DEFAULT_REASON = {
    "sq": "ky termin nuk mund të rezervohet ose ndryshohet online.",
    "en": "this appointment cannot be booked or changed online.",
    "de": "dieser Termin kann online nicht gebucht oder geändert werden.",
}


def render(key, language, **params):
    return TEMPLATES[key][language].format(**params)


def format_datetime(value, language):
    """``value`` must already be in the clinic's time zone."""
    return _DATETIME[language].format(
        weekday=WEEKDAYS[language][value.weekday()],
        date=value.strftime("%d.%m.%Y"),
        time=value.strftime("%H:%M"),
    )


def join(items, language):
    items = list(items)
    if len(items) <= 1:
        return "".join(items)
    return f"{', '.join(items[:-1])} {_AND[language]} {items[-1]}"


def reason(code, language):
    return REASONS.get(code, _DEFAULT_REASON)[language]


def contact(clinic, language):
    if clinic.phone:
        return render("contact_phone", language, phone=clinic.phone)
    if clinic.email:
        return render("contact_email", language, email=clinic.email)
    return render("contact_none", language)
