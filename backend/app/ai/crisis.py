"""Does a query suggest the person may be thinking about suicide or self-harm?

A short list of plain phrases, checked on every parse whichever parser answers. The LLM
can also raise the flag (ParsedQuery.crisis) for wording no list could anticipate; either
one is enough. The flag only shows helpline information above the search, which still
works as usual, so the list leans towards flagging: "suicide" alone counts, even in
"suicide prevention". A false alarm costs a calm message; a miss costs much more.

Nothing here is logged or stored: not the query, not the result.
"""

import re

_PHRASES = (
    r"suicid\w*",
    r"kill(?:ing)? my ?self",
    r"end(?:ing)? (?:it all|my (?:own )?life)",
    r"take my (?:own )?life",
    r"(?:want|wanted|wanting|wanna) to die",
    r"wanna die",
    r"wish i (?:was|were) dead",
    r"better off dead",
    r"(?:do not|don't|dont) want to (?:live|be alive|be here anymore|wake up)",
    r"no reason to live",
    r"self[- ]?harm\w*",
    r"self[- ]?injur\w*",
    r"(?:hurt|hurting|harm|harming|cut|cutting) my ?self",
)
_PATTERN = re.compile(r"\b(?:" + "|".join(_PHRASES) + r")\b")


def mentions_self_harm(query: str) -> bool:
    # Curly apostrophes (common on phones) become straight ones before matching.
    text = " ".join(query.lower().replace("’", "'").split())
    return _PATTERN.search(text) is not None
