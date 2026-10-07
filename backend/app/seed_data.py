"""Declarative demo data for `app.seed`. Receipts, watermarks, history ranges and
last_message_at are *derived* from this by the seed, never written by hand.

Read state is described per member as "tails" counted back from the end of the
messages that member can see:
  unread_tail=3       -> the last 3 visible messages are not read by this member
  undelivered_tail=1  -> the last visible message has not reached this member
Tails may only cover messages sent by *other* people (the seed checks this).
"""

from dataclasses import dataclass

from app.models.enums import ConversationType, MemberRole

DEMO_PHONE = "+15550100001"  # Alex Rivera, documented as the demo login
SECOND_DEMO_PHONE = "+15550100002"  # Priya Sharma, for two-browser testing


@dataclass(frozen=True)
class SeedUser:
    key: str
    phone: str
    display_name: str
    about: str
    last_seen_minutes_ago: int
    username: str | None = None
    read_receipts: bool = True


@dataclass(frozen=True)
class Say:
    sender: str
    text: str
    minutes_ago: float


@dataclass(frozen=True)
class Event:
    """A system message, e.g. "Alex removed Daniel"."""

    actor: str
    event: str
    minutes_ago: float
    targets: tuple[str, ...] = ()
    label: str | None = None  # referenced by SeedMember.added_by / removed_by


ScriptItem = Say | Event


@dataclass(frozen=True)
class SeedMember:
    user: str
    role: MemberRole = MemberRole.MEMBER
    added_by: str | None = None  # label of the Event that added them later (None = founding member)
    removed_by: str | None = None  # label of the Event that removed them
    unread_tail: int = 0
    undelivered_tail: int = 0


@dataclass(frozen=True)
class SeedConversation:
    key: str
    type: ConversationType
    creator: str
    members: tuple[SeedMember, ...]
    script: tuple[ScriptItem, ...]
    name: str | None = None


@dataclass(frozen=True)
class SeedContact:
    owner: str
    contact: str
    nickname: str | None = None


@dataclass(frozen=True)
class SeedBlock:
    blocker: str
    blocked: str
    minutes_ago: float


USERS: tuple[SeedUser, ...] = (
    SeedUser("alex", DEMO_PHONE, "Alex Rivera", "Coffee first ☕", 2, username="alex.01"),
    SeedUser("priya", SECOND_DEMO_PHONE, "Priya Sharma", "Reading, always 📚", 5, username="priya.22"),
    SeedUser("marcus", "+15550100003", "Marcus Chen", "Out cycling 🚴", 45),
    SeedUser("sofia", "+15550100004", "Sofia Rossi", "Ciao!", 9),
    SeedUser("daniel", "+15550100005", "Daniel Okafor", "Busy week", 180, username="dan.okafor"),
    SeedUser("emma", "+15550100006", "Emma Larsen", "Travelling ✈️", 2880),
    SeedUser("hiro", "+15550100007", "Hiro Tanaka", "Sci-fi nerd", 30),
    SeedUser("lena", "+15550100008", "Lena Fischer", "Privacy matters", 60, read_receipts=False),
    SeedUser("spammer", "+15550199999", "Crypto Deals", "DM me for 100x 🚀", 4000),
    SeedUser("maya", "+15550000001", "Maya (bot)", "Demo bot - I reply to your messages", 0),
    SeedUser("leo", "+15550000002", "Leo (bot)", "Demo bot - say hi!", 0),
)

CONTACTS: tuple[SeedContact, ...] = (
    *(SeedContact("alex", key) for key in ("priya", "marcus", "sofia", "daniel", "emma", "lena", "maya", "leo")),
    *(SeedContact("priya", key) for key in ("alex", "marcus", "lena", "hiro")),
    *(SeedContact("marcus", key) for key in ("alex", "priya")),
    *(SeedContact(key, "alex") for key in ("sofia", "daniel", "emma", "lena")),
)

BLOCKS: tuple[SeedBlock, ...] = (SeedBlock("alex", "spammer", minutes_ago=2880),)


def _chat(pairs: list[tuple[str, str]], start_minutes_ago: float, gap_minutes: float = 2) -> tuple[Say, ...]:
    """A burst of messages starting `start_minutes_ago`, `gap_minutes` apart."""
    return tuple(Say(sender, text, start_minutes_ago - i * gap_minutes) for i, (sender, text) in enumerate(pairs))


def _dm(
    key: str,
    a: str,
    b: str,
    script: tuple[ScriptItem, ...],
    unread_tail: int = 0,
    undelivered_tail: int = 0,
) -> SeedConversation:
    """A DM started by `a`; the tails describe what `b` hasn't received/read yet."""
    return SeedConversation(
        key=key,
        type=ConversationType.DIRECT,
        creator=a,
        members=(SeedMember(a), SeedMember(b, unread_tail=unread_tail, undelivered_tail=undelivered_tail)),
        script=script,
    )


_PRIYA_DAY_1 = [
    ("priya", "Hey! Are you coming to the book swap on Saturday?"),
    ("alex", "Planning to! What time does it start?"),
    ("priya", "10am at the library café"),
    ("alex", "Perfect, I'll bring a couple of thrillers"),
    ("priya", "Bring the Tana French one if you're done with it"),
    ("alex", "Finished it last night. That ending 😳"),
    ("priya", "Right?? No spoilers for Lena though, she just started"),
    ("alex", "My lips are sealed 🤐"),
    ("priya", "Also, did you see the new café opened on 5th?"),
    ("alex", "Not yet, any good?"),
    ("priya", "Their cardamom buns are unreal"),
    ("alex", "Say no more, going tomorrow"),
    ("priya", "Report back!"),
    ("alex", "Will do 🫡"),
    ("priya", "Gotta run, talk later"),
    ("alex", "Bye!"),
    ("priya", "Oh wait - can you send me Marcus's number?"),
    ("alex", "Sure, just shared his contact"),
    ("priya", "Thanks!"),
    ("alex", "👍"),
]
_PRIYA_DAY_2 = [
    ("alex", "Okay the cardamom buns are dangerous"),
    ("priya", "Told you 😂"),
    ("alex", "I bought four"),
    ("priya", "FOUR"),
    ("alex", "For the week. Allegedly"),
    ("priya", "How many are left?"),
    ("alex", "...one"),
    ("priya", "Iconic"),
    ("alex", "Are you free Thursday evening?"),
    ("priya", "Should be, what's up?"),
    ("alex", "Thinking of trying that new ramen place"),
    ("priya", "Yes please, I'm in"),
    ("alex", "7pm?"),
    ("priya", "7 works"),
    ("alex", "I'll book a table"),
    ("priya", "Amazing, see you then"),
    ("alex", "Booked ✅"),
    ("priya", "You're the best"),
]
_PRIYA_DAY_3 = [
    ("priya", "That ramen was incredible"),
    ("alex", "Best broth I've had in ages"),
    ("priya", "We need to go back with the book club crew"),
    ("alex", "Agreed. I'll suggest it in the group"),
    ("priya", "Also I finished the Tana French"),
    ("alex", "And??"),
    ("priya", "I need a week to recover"),
    ("alex", "Haha I warned you"),
    ("priya", "What should I read next?"),
    ("alex", "Project Hail Mary. Trust me"),
    ("priya", "Ooh that could be the next book club pick"),
    ("alex", "Do it!"),
    ("priya", "Adding it to the poll"),
    ("alex", "🙌"),
    ("priya", "Okay heading to bed, night!"),
    ("alex", "Night 🌙"),
    ("priya", "Morning! Coffee later?"),
    ("alex", "Always ☕"),
]

CONVERSATIONS: tuple[SeedConversation, ...] = (
    # 56 messages over three days: more than one page (50), so "load older" has work to do.
    _dm(
        "dm-alex-priya",
        "alex",
        "priya",
        _chat(_PRIYA_DAY_1, 4320) + _chat(_PRIYA_DAY_2, 2880) + _chat(_PRIYA_DAY_3, 1440, gap_minutes=40),
    ),
    # Last outgoing message read (filled double tick).
    _dm(
        "dm-alex-marcus",
        "alex",
        "marcus",
        _chat(
            [
                ("marcus", "Ride on Sunday?"),
                ("alex", "If it's not raining, yes"),
                ("marcus", "Forecast says sunny"),
                ("alex", "Then I'm in. Usual route?"),
                ("marcus", "Let's do the lake loop for a change"),
                ("alex", "Lake loop it is. 8am at the bridge"),
            ],
            105,
        ),
    ),
    # Last outgoing message delivered but not read.
    _dm(
        "dm-alex-daniel",
        "alex",
        "daniel",
        _chat(
            [
                ("daniel", "Sorry I had to drop out of the trip"),
                ("alex", "No worries at all, work comes first"),
                ("daniel", "Next one for sure"),
                ("alex", "Holding you to that!"),
                ("alex", "Send me the photos from the conference when you can"),
            ],
            48,
        ),
        unread_tail=1,
    ),
    # Last outgoing message only sent: Emma hasn't been online.
    _dm(
        "dm-alex-emma",
        "alex",
        "emma",
        _chat(
            [
                ("emma", "Landed in Oslo! 🇳🇴"),
                ("alex", "Welcome home! How was the flight?"),
                ("emma", "Long but fine"),
                ("alex", "Did you get my postcard from Lisbon?"),
            ],
            31,
        ),
        unread_tail=1,
        undelivered_tail=1,
    ),
    # Three unread incoming messages for Alex.
    SeedConversation(
        key="dm-alex-sofia",
        type=ConversationType.DIRECT,
        creator="sofia",
        members=(SeedMember("sofia"), SeedMember("alex", unread_tail=3)),
        script=_chat(
            [
                ("sofia", "Are you around this weekend?"),
                ("alex", "Saturday yes, Sunday I'm riding with Marcus"),
                ("sofia", "Saturday works!"),
                ("alex", "Brunch?"),
                ("sofia", "Yes!! The place by the river?"),
                ("sofia", "I'll book for 11"),
                ("sofia", "Also bring your camera, the market is on 📷"),
            ],
            20,
        ),
    ),
    # Lena has read receipts off: delivered, never shown as read.
    _dm(
        "dm-alex-lena",
        "alex",
        "lena",
        _chat(
            [
                ("lena", "Did you switch to the new password manager?"),
                ("alex", "Yes, migrated everything last night"),
                ("lena", "Nice. Turn on 2FA for the vault too"),
                ("alex", "Done ✅ thanks for the nudge"),
            ],
            310,
        ),
    ),
    _dm(
        "dm-alex-maya",
        "alex",
        "maya",
        _chat(
            [
                ("maya", "Hi! I'm Maya, a demo bot. Send me a message and I'll reply 🙂"),
                ("alex", "Hi Maya!"),
                ("maya", "Hey Alex! Nice to meet you 👋"),
            ],
            600,
        ),
    ),
    _dm(
        "dm-alex-leo",
        "alex",
        "leo",
        _chat(
            [
                ("leo", "Leo here, the other demo bot. Ask me anything!"),
                ("alex", "Is this thing on?"),
                ("leo", "Loud and clear 📡"),
            ],
            650,
        ),
    ),
    # Spammer messaged before Alex blocked them (block at 2880 minutes ago).
    SeedConversation(
        key="dm-spammer-alex",
        type=ConversationType.DIRECT,
        creator="spammer",
        members=(SeedMember("spammer"), SeedMember("alex")),
        script=(
            Say("spammer", "Hi dear, want to 100x your savings? 🚀", 3000),
            Say("spammer", "Limited spots, reply YES", 2990),
        ),
    ),
    # A chat Alex isn't in, so the second demo login has its own conversation.
    _dm(
        "dm-priya-marcus",
        "priya",
        "marcus",
        _chat(
            [
                ("priya", "Hey Marcus, Alex gave me your number"),
                ("marcus", "Hi Priya! What's up?"),
                ("priya", "Book club is looking for one more member"),
                ("marcus", "Not much of a reader but I'll try 😄"),
                ("priya", "Perfect, I'll add you next month"),
            ],
            1300,
        ),
    ),
    # Daniel was removed (sees nothing after his removal); Emma was added later
    # (sees nothing before she was added). Marcus hasn't read the last message,
    # so Alex sees it as delivered.
    SeedConversation(
        key="group-weekend-trip",
        type=ConversationType.GROUP,
        name="Weekend Trip",
        creator="alex",
        members=(
            SeedMember("alex", role=MemberRole.ADMIN),
            SeedMember("priya"),
            SeedMember("marcus", unread_tail=1),
            SeedMember("sofia"),
            SeedMember("daniel", removed_by="daniel-removed"),
            SeedMember("emma", added_by="emma-added"),
        ),
        script=(
            Event("alex", "group_created", 1500),
            Say("alex", "Booked the cabin for the 18th 🎉", 1490),
            Say("priya", "Amazing! How many beds?", 1486),
            Say("alex", "Four rooms, so two of us share", 1482),
            Say("marcus", "I can drive, my car fits four", 1470),
            Say("daniel", "Count me out this time, sorry 😕", 1200),
            Event("alex", "member_removed", 1190, targets=("daniel",), label="daniel-removed"),
            Event("alex", "member_added", 900, targets=("emma",), label="emma-added"),
            Say("emma", "Thanks for adding me! What should I bring?", 890),
            Say("sofia", "Snacks and board games 😄", 880),
            Say("alex", "I'll make a shopping list tonight", 60),
        ),
    ),
    # Five unread for Alex.
    SeedConversation(
        key="group-book-club",
        type=ConversationType.GROUP,
        name="Book Club",
        creator="priya",
        members=(
            SeedMember("priya", role=MemberRole.ADMIN),
            SeedMember("alex", unread_tail=5),
            SeedMember("lena"),
            SeedMember("hiro"),
        ),
        script=(
            Event("priya", "group_created", 2000),
            Say("priya", "This month's pick: Project Hail Mary 📚", 1990),
            Say("alex", "Love it, already halfway through", 1900),
            Say("lena", "Starting tonight!", 400),
            Say("hiro", "Chapter 12 was wild", 50),
            Say("priya", "No spoilers Hiro 😂", 45),
            Say("lena", "Meeting Sunday at 6?", 30),
            Say("hiro", "Works for me", 20),
            Say("priya", "Booked a table at the café", 15),
        ),
    ),
    # A group with a bot, so group read receipts can be demoed with one browser.
    SeedConversation(
        key="group-recipe-swap",
        type=ConversationType.GROUP,
        name="Recipe Swap",
        creator="alex",
        members=(SeedMember("alex", role=MemberRole.ADMIN), SeedMember("maya")),
        script=(
            Event("alex", "group_created", 700),
            Say("alex", "Share your best weeknight dinner!", 690),
            Say("maya", "Lemon garlic pasta, 15 minutes, never fails 🍋", 689),
        ),
    ),
)

# Expected unread counts for the demo user (checked by tests).
EXPECTED_DEMO_UNREAD = {"dm-alex-sofia": 3, "group-book-club": 5}

