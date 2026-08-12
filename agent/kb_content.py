"""
Seed content for the RAG knowledge base -- a fictional small business
(Willow Lane Hair Studio), hand-authored for this demo since there's no
real business to pull FAQ content from.

Each entry becomes one row in kb_documents; seed_kb.py (next step) embeds
and chunks these into kb_chunks. Kept short and FAQ-style on purpose --
each entry is already close to one retrieval-sized chunk, so minimal
splitting is needed.

Review/edit this before it gets loaded -- nothing's embedded or persisted
yet, this is just the source content.
"""

KB_DOCUMENTS = [
    {
        "title": "Business hours",
        "content": (
            "Willow Lane Hair Studio is open Tuesday through Saturday, "
            "9:00 AM to 6:00 PM. We're closed Sundays and Mondays, and "
            "closed on major public holidays."
        ),
    },
    {
        "title": "Services and pricing",
        "content": (
            "We offer: Haircuts ($45), Haircut + Beard Trim ($55), Hair "
            "Coloring (starting at $90, price depends on hair length and "
            "technique), Blowout/Styling ($35), Kids' Haircuts under 12 "
            "($30). Final pricing for coloring services is confirmed "
            "during an in-person consultation."
        ),
    },
    {
        "title": "Booking and appointments",
        "content": (
            "Appointments can be booked by phone. We recommend booking "
            "at least 2-3 days in advance, especially for weekend slots. "
            "Walk-ins are welcome but subject to stylist availability."
        ),
    },
    {
        "title": "Cancellation and rescheduling policy",
        "content": (
            "You can cancel or reschedule up to 4 hours before your "
            "appointment with no charge. Cancellations with less than 4 "
            "hours notice, or no-shows, may be charged a $20 fee applied "
            "to your next visit."
        ),
    },
    {
        "title": "Location and parking",
        "content": (
            "We're located at 128 Willow Lane, Suite 3. Free street "
            "parking is available on Willow Lane, and there's a public "
            "parking lot one block away on Cedar Street."
        ),
    },
    {
        "title": "First-time visitors",
        "content": (
            "New clients should arrive 10 minutes before their scheduled "
            "time to fill out a brief intake form. No preparation is "
            "needed -- just come as you are. If you have a specific style "
            "in mind, feel free to bring a reference photo."
        ),
    },
    {
        "title": "Late arrivals",
        "content": (
            "If you're running more than 15 minutes late, we may need to "
            "shorten your service or reschedule, depending on the next "
            "appointment on the schedule. Please call ahead if you know "
            "you'll be late."
        ),
    },
    {
        "title": "Payment methods",
        "content": (
            "We accept cash, all major credit/debit cards, and Apple Pay "
            "/ Google Pay. We do not accept personal checks."
        ),
    },
    {
        "title": "Products and allergies",
        "content": (
            "We use professional-grade products from Wella and Oribe. If "
            "you have known allergies or sensitivities, please let your "
            "stylist know before your service so they can select suitable "
            "products or do a patch test."
        ),
    },
    {
        "title": "Gift cards",
        "content": (
            "Gift cards are available for purchase in-salon in any amount, "
            "and do not expire."
        ),
    },
    {
        "title": "Children's haircuts",
        "content": (
            "We welcome children of all ages. Kids' haircuts (12 and "
            "under) are $30 and typically take about 20 minutes."
        ),
    },
    {
        "title": "Contact and escalation",
        "content": (
            "For anything outside standard bookings, questions, or "
            "policies -- such as complaints, special accommodations, or "
            "billing disputes -- a team member will follow up directly "
            "rather than being handled automatically."
        ),
    },
]
