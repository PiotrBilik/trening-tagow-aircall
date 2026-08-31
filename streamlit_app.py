from __future__ import annotations

import random
import re

import streamlit as st


st.set_page_config(
    page_title="Trening tagów",
    page_icon="🏷️",
    layout="centered",
)


# Nazwy i kolory tagów odwzorowują panel „Select tags" w Aircallu (zrzuty z 31.08.2026),
# żeby trening wyglądał tak samo jak realna praca po rozmowie.
# Logika statusów: TaskAircallParseHelper.deriveStatusFromTags w orgu produkcyjnym.

TAGI = [
    {"nazwa": "Conversion attempt made", "tlo": "#8cc9a9", "tekst": "#14342a"},
    {"nazwa": "Declared one-time", "tlo": "#106b4f", "tekst": "#ffffff"},
    {"nazwa": "Declared recurring", "tlo": "#7fb894", "tekst": "#14342a"},
    {"nazwa": "Declared Renewal", "tlo": "#c9a227", "tekst": "#3a2f05"},
    {"nazwa": "Declared Upgrade", "tlo": "#b8a2da", "tekst": "#2c2140"},
    {"nazwa": "Do not call", "tlo": "#c0392b", "tekst": "#ffffff"},
    {"nazwa": "Do not send email", "tlo": "#aec0da", "tekst": "#22314a"},
    {"nazwa": "Fail", "tlo": "#8e2b2b", "tekst": "#ffffff"},
    {"nazwa": "Need to call another time", "tlo": "#eaa08f", "tekst": "#4a231a"},
    {"nazwa": "Number unavailable", "tlo": "#123c48", "tekst": "#ffffff"},
    {"nazwa": "Other", "tlo": "#123c48", "tekst": "#ffffff"},
    {"nazwa": "Success", "tlo": "#7fc39b", "tekst": "#14342a"},
    {"nazwa": "Undecided", "tlo": "#58b1e0", "tekst": "#10344a"},
    {"nazwa": "Voicemail", "tlo": "#123c48", "tekst": "#ffffff"},
]

ALL_TAGS = [t["nazwa"] for t in TAGI]

TAG_RULES = {
    "Conversion attempt made": "Dodaj zawsze, gdy w rozmowie poprosiłaś o wsparcie. Statusu nie zmienia, ale dzięki niemu wiemy, ile razy prośba padła.",
    "Declared one-time": "Darczyńca obiecał jednorazową wpłatę. Zapisze się *Promised one-time*.",
    "Declared recurring": "Darczyńca obiecał wpłacać co miesiąc. Zapisze się *Promised recurring*.",
    "Declared Renewal": "Darczyńca obiecał odnowić swoje wsparcie. Zapisze się *Promised renewal*.",
    "Declared Upgrade": "Darczyńca obiecał podnieść kwotę. Zapisze się *Promised upgrade*.",
    "Do not call": "Prosi, żeby więcej nie dzwonić. Liczy się jak rozmowa nieudana, zapisze się *Failed*.",
    "Do not send email": "Prosi, żeby nie wysyłać mu maili. Statusu nie zmienia.",
    "Fail": "Prośba padła, ale darczyńca odmówił. Zapisze się *Failed*.",
    "Need to call another time": "Trzeba zadzwonić jeszcze raz, innym razem. Zapisze się *Postponed*.",
    "Number unavailable": "Numer nie działa albo jest błędny. Zapisze się *Cannot be reached*.",
    "Other": "Nic z listy nie pasuje, bo sytuacja była nietypowa. Statusu nie zmienia.",
    "Success": (
        "Obietnica została spełniona od razu, w trakcie rozmowy. "
        "**Dodawaj go tylko razem z tagiem `Declared ...`** — sam z siebie nic nie zapisze."
    ),
    "Undecided": "Darczyńca się waha i chce to przemyśleć. Zapisze się *Undecided*.",
    "Voicemail": "Odezwała się poczta głosowa. Zapisze się *Didn't answer*, a system sam zaplanuje kolejną próbę.",
}


def derive_status(tags: set[str]) -> str:
    """Wierne odwzorowanie TaskAircallParseHelper.deriveStatusFromTags.

    Kolejność warunków ma znaczenie — pierwszy pasujący wygrywa.
    """
    t = {x.lower() for x in tags}

    if {"declared renewal", "declared upgrade", "success"} <= t:
        return "Success renewal"
    if {"declared renewal", "success"} <= t:
        return "Success renewal"
    if {"declared one-time", "success"} <= t:
        return "Success one-time"
    if {"declared recurring", "success"} <= t:
        return "Success recurring"
    if {"declared upgrade", "success"} <= t:
        return "Success upgrade"
    if {"declared renewal", "declared upgrade"} <= t:
        return "Promised renewal"
    if "fail" in t or "do not call" in t:
        return "Failed"
    if "voicemail" in t:
        return "Didn't answer"
    if "number unavailable" in t:
        return "Cannot be reached"
    if "need to call another time" in t:
        return "Postponed"
    if "undecided" in t:
        return "Undecided"
    if "declared one-time" in t:
        return "Promised one-time"
    if "declared recurring" in t:
        return "Promised recurring"
    if "declared upgrade" in t:
        return "Promised upgrade"
    if "declared renewal" in t:
        return "Promised renewal"
    return ""


SCENARIOS = [
    {
        "title": "Darowizna miesięczna zadeklarowana, ale niepotwierdzona",
        "story": (
            "Poprosiłaś o darowiznę miesięczną i darczyńca się zgodził. "
            "Rozmowa skończyła się, zanim wpłata została dopięta."
        ),
        "correct_tags": {"Conversion attempt made", "Declared recurring"},
        "why": "Obietnica padła, ale nie została spełniona w rozmowie, więc bez `Success`.",
    },
    {
        "title": "Darowizna miesięczna zadeklarowana i potwierdzona",
        "story": (
            "Poprosiłaś o darowiznę miesięczną, darczyńca się zgodził "
            "i od razu w rozmowie wszystko potwierdził."
        ),
        "correct_tags": {"Conversion attempt made", "Declared recurring", "Success"},
        "why": "Prośba padła, darczyńca obiecał miesięczną wpłatę i od razu ją potwierdził.",
    },
    {
        "title": "Darowizna jednorazowa potwierdzona",
        "story": (
            "Darczyńca nie chciał wpłacać co miesiąc, ale zgodził się wesprzeć jednorazowo. "
            "Przelew zrobił jeszcze w trakcie rozmowy."
        ),
        "correct_tags": {"Conversion attempt made", "Declared one-time", "Success"},
        "why": "Darczyńca obiecał jednorazową wpłatę i od razu ją zrobił.",
    },
    {
        "title": "Darczyńca mówi: może później",
        "story": (
            "Rozmowa się odbyła i poprosiłaś o darowiznę miesięczną. "
            "Darczyńca nie powiedział ani tak, ani nie. Chce to przemyśleć."
        ),
        "correct_tags": {"Conversion attempt made", "Undecided"},
        "why": "Prośba padła, ale darczyńca niczego nie obiecał ani nie odmówił.",
    },
    {
        "title": "Darczyńca odmówił po złożeniu prośby",
        "story": "Rozmowa się odbyła, poprosiłaś o wsparcie, a darczyńca wyraźnie odmówił.",
        "correct_tags": {"Conversion attempt made", "Fail"},
        "why": "Prośba padła i skończyła się odmową.",
    },
    {
        "title": "Prośba o oddzwonienie przed złożeniem prośby",
        "story": (
            "Darczyńca odebrał, ale był zajęty i poprosił o telefon w innym terminie. "
            "Nie zdążyłaś nawet poprosić o wsparcie."
        ),
        "correct_tags": {"Need to call another time"},
        "why": "Prośba o wsparcie jeszcze nie padła, więc bez `Conversion attempt made`.",
    },
    {
        "title": "Oddzwonienie po złożeniu prośby",
        "story": (
            "Poprosiłaś o wsparcie, ale darczyńca nie zdążył odpowiedzieć. "
            "Niczego nie obiecał i poprosił, żeby zadzwonić innym razem."
        ),
        "correct_tags": {"Conversion attempt made", "Need to call another time"},
        "why": (
            "Prośba padła, więc jest `Conversion attempt made`. "
            "Darczyńca nic nie obiecał, więc żaden tag `Declared ...` tu nie wchodzi."
        ),
    },
    {
        "title": "Poczta głosowa",
        "story": "Zamiast darczyńcy odezwała się poczta głosowa. Rozmowy nie było.",
        "correct_tags": {"Voicemail"},
        "why": "Nie było rozmowy. System sam zaplanuje kolejną próbę w Twoim kalendarzu.",
    },
    {
        "title": "Nieprawidłowy albo niedostępny numer",
        "story": "Nie udało się połączyć, bo numer był błędny albo nieaktywny.",
        "correct_tags": {"Number unavailable"},
        "why": "To problem z dodzwonieniem się, a nie wynik rozmowy.",
    },
    {
        "title": "Odnowienie zadeklarowane i potwierdzone",
        "story": (
            "Dzwoniłaś w sprawie odnowienia wsparcia. Darczyńca zgodził się odnowić "
            "i od razu to potwierdził."
        ),
        "correct_tags": {"Conversion attempt made", "Declared Renewal", "Success"},
        "why": "Darczyńca obiecał odnowić wsparcie i od razu to potwierdził.",
    },
    {
        "title": "Odnowienie plus upgrade zadeklarowane, ale niepotwierdzone",
        "story": (
            "Dzwoniłaś w sprawie odnowienia. Darczyńca zgodził się odnowić wsparcie "
            "i przy okazji podnieść kwotę, ale nic nie zostało jeszcze dopięte."
        ),
        "correct_tags": {
            "Conversion attempt made",
            "Declared Renewal",
            "Declared Upgrade",
        },
        "why": (
            "Zaznaczasz obie obietnice, bo obie padły. Zapisze się *Promised renewal*, "
            "bo odnowienie jest ważniejsze niż podwyżka."
        ),
    },
    {
        "title": "Odnowienie plus upgrade zadeklarowane i potwierdzone",
        "story": (
            "Dzwoniłaś w sprawie odnowienia. Darczyńca odnowił wsparcie, zgodził się też "
            "podnieść kwotę i obie rzeczy potwierdził w rozmowie."
        ),
        "correct_tags": {
            "Conversion attempt made",
            "Declared Renewal",
            "Declared Upgrade",
            "Success",
        },
        "why": (
            "Obie obietnice padły i obie zostały spełnione. Zapisze się *Success renewal*, "
            "bo odnowienie jest ważniejsze niż podwyżka."
        ),
    },
    {
        "title": "Upgrade zadeklarowany, ale jeszcze niepotwierdzony",
        "story": (
            "Poprosiłaś o podniesienie kwoty i darczyńca się wstępnie zgodził, "
            "ale nic jeszcze nie zostało dopięte."
        ),
        "correct_tags": {"Conversion attempt made", "Declared Upgrade"},
        "why": "Podwyżka jest obiecana, ale jeszcze niepotwierdzona, więc bez `Success`.",
    },
    {
        "title": "Prośba o brak dalszych telefonów",
        "story": (
            "Poprosiłaś o wsparcie, darczyńca odmówił i dodatkowo poprosił, "
            "żeby już więcej do niego nie dzwonić."
        ),
        "correct_tags": {"Conversion attempt made", "Fail", "Do not call"},
        "why": "Prośba padła, skończyła się odmową, a darczyńca prosi o brak kolejnych telefonów.",
    },
    {
        "title": "Sytuacja nietypowa",
        "story": (
            "Udało się dodzwonić, ale rozmowa w ogóle nie dotyczyła wsparcia. "
            "Osoba chciała załatwić inną sprawę i nie było sensu o nic prosić."
        ),
        "correct_tags": {"Other"},
        "why": "Nic z listy nie pasuje, a o wsparcie nie prosiłaś.",
    },
    {
        "title": "Prośba o niewysyłanie maili",
        "story": (
            "Rozmowa poszła dobrze, darczyńca obiecał wpłacać co miesiąc i od razu to "
            "potwierdził. Przy okazji poprosił, żeby nie wysyłać mu maili."
        ),
        "correct_tags": {
            "Conversion attempt made",
            "Declared recurring",
            "Success",
            "Do not send email",
        },
        "why": (
            "Wynik rozmowy tagujesz normalnie, a `Do not send email` dokładasz obok. "
            "Ten tag sam nie zmienia statusu."
        ),
    },
]

ZASADY = [
    "Tagi opisują wynik rozmowy. Nic poza nimi nie musisz uzupełniać.",
    "Poprosiłaś o wsparcie? Dodaj `Conversion attempt made`.",
    "Darczyńca coś obiecał? Dodaj pasujący tag `Declared ...`.",
    "`Success` tylko razem z `Declared ...` i tylko gdy obietnica została od razu spełniona.",
    "`Fail` gdy prośba padła i darczyńca odmówił.",
    "`Need to call another time` gdy prośba jeszcze nie padła.",
]


def na_html(tekst: str) -> str:
    """Zamienia prosty markdown na HTML, bo opisy w ściądze renderujemy sami."""
    tekst = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", tekst)
    tekst = re.sub(r"\*(.+?)\*", r"<em>\1</em>", tekst)
    tekst = re.sub(r"`(.+?)`", r"<code>\1</code>", tekst)
    return tekst


def slug(nazwa: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", nazwa.lower()).strip("_")


def css_tagow() -> str:
    reguly = [
        """
        div[data-testid="stElementContainer"][class*="st-key-tag_"] button {
            border-radius: 999px; border: 2px solid transparent;
            padding: .22rem .72rem; min-height: 0; font-weight: 600;
            font-size: .82rem; line-height: 1.2; white-space: nowrap;
            transition: none;
        }
        .st-key-pigulki { flex-wrap: wrap; align-items: flex-start; }
        div[class*="st-key-tag_"] button { opacity: .58; }
        div[class*="st-key-tag_"] button:hover { opacity: .85; }
        """
    ]
    for tag in TAGI:
        s = slug(tag["nazwa"])
        reguly.append(
            f'''
            div[data-testid="stElementContainer"][class*="st-key-tag_{s}"] button,
            div[data-testid="stElementContainer"][class*="st-key-tag_{s}"] button:hover,
            div[data-testid="stElementContainer"][class*="st-key-tag_{s}"] button:focus,
            div[data-testid="stElementContainer"][class*="st-key-tag_{s}"] button:active {{
                background-color: {tag["tlo"]} !important;
                color: {tag["tekst"]} !important;
            }}
            div[data-testid="stElementContainer"][class*="st-key-tag_{s}"] button p {{
                color: {tag["tekst"]} !important; font-weight: 600;
            }}
            '''
        )
    return "".join(reguly)


st.markdown(
    f"""
    <style>
      /* górny pasek Streamlita jest position: fixed i ma ~3.75rem,
         padding-top musi go przekroczyć, inaczej treść wjeżdża pod niego */
      .block-container {{padding-top: 4.2rem; padding-bottom: 2rem; max-width: 46rem;}}
      div[data-testid="stAppDeployButton"] {{display: none;}}
      div[data-testid="stMarkdownContainer"] p {{line-height: 1.45; margin-bottom: .25rem;}}
      div[data-testid="stMarkdownContainer"] code {{
          background: rgba(120,120,120,.14); padding: .05em .34em;
          border-radius: .35rem; font-size: .86em;
      }}
      section[data-testid="stSidebar"] div[data-testid="stMarkdownContainer"] p {{
          font-size: .86rem; line-height: 1.45;
      }}
      div[data-testid="stAlert"] {{padding: .5rem .8rem;}}
      hr {{margin: .5rem 0;}}
      .naglowek {{font-weight: 700; font-size: 1rem; margin-bottom: .1rem;}}
      .wymagane {{color: #e5533d; font-weight: 600; margin-left: .45rem; font-size: .85rem;}}
      .sekcja {{font-size: .8rem; opacity: .7; font-weight: 600; margin: .5rem 0 .1rem;}}
      .sytuacja {{font-size: .95rem; line-height: 1.5;}}
      .sciaga-poz {{margin: 0 0 .7rem;}}
      .sciaga-tag {{
          display: inline-block; border-radius: 999px; padding: .1rem .6rem;
          font-size: .78rem; font-weight: 600; margin-bottom: .18rem;
      }}
      .sciaga-opis {{font-size: .82rem; line-height: 1.45; opacity: .82;}}
      .sciaga-opis code {{font-size: .95em;}}
      {css_tagow()}
    </style>
    """,
    unsafe_allow_html=True,
)


def init_state() -> None:
    if "kolejnosc" not in st.session_state:
        nowa_runda()
    st.session_state.setdefault("wyniki", {})
    st.session_state.setdefault("wybor", {})
    st.session_state.setdefault("uzycia", {})


def nowa_runda() -> None:
    st.session_state.indeks = 0
    kolejnosc = list(range(len(SCENARIOS)))
    random.shuffle(kolejnosc)
    st.session_state.kolejnosc = kolejnosc
    st.session_state.zaliczone = set()
    st.session_state.wyniki = {}
    st.session_state.wybor = {}


def przelacz_tag(skey: str, tag: str) -> None:
    biezace = set(st.session_state.wybor.get(skey, set()))
    if tag in biezace:
        biezace.discard(tag)
    else:
        biezace.add(tag)
        st.session_state.uzycia[tag] = st.session_state.uzycia.get(tag, 0) + 1
    st.session_state.wybor[skey] = biezace


init_state()

# ---------------------------------------------------------------- pasek boczny

with st.sidebar:
    st.markdown("### Ściąga")
    st.info(
        "Po rozmowie zaznaczasz tagi i to jedyne, co robisz ręcznie. Resztę system "
        "robi sam: ustawia status darczyńcy, planuje kolejny telefon i zapisuje "
        "podsumowanie rozmowy.",
        icon="💡",
    )

    with st.expander("Co robi każdy tag", expanded=False):
        for tag in TAGI:
            st.markdown(
                f'<div class="sciaga-poz">'
                f'<span class="sciaga-tag" style="background:{tag["tlo"]};'
                f'color:{tag["tekst"]}">{tag["nazwa"]}</span>'
                f'<div class="sciaga-opis">{na_html(TAG_RULES[tag["nazwa"]])}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

    with st.expander("Zasady w skrócie", expanded=False):
        for zasada in ZASADY:
            st.markdown(
                f'<div class="sciaga-opis" style="margin-bottom:.5rem">• {na_html(zasada)}</div>',
                unsafe_allow_html=True,
            )

# ------------------------------------------------------------------- nagłówek

indeks = st.session_state.indeks
scenario = SCENARIOS[st.session_state.kolejnosc[indeks]]
skey = scenario["title"]
selected = set(st.session_state.wybor.get(skey, set()))
ostatnie = indeks >= len(SCENARIOS) - 1

st.markdown("##### 🏷️ Trening tagów")
st.progress(
    (indeks + 1) / len(SCENARIOS),
    text=f"Rozmowa {indeks + 1} z {len(SCENARIOS)} · trafione {len(st.session_state.zaliczone)}",
)

# ------------------------------------------------------------------- scenariusz

with st.container(border=True):
    st.markdown(f'<div class="sytuacja">{scenario["story"]}</div>', unsafe_allow_html=True)

# ------------------------------------------------- panel tagowania jak w Aircallu

with st.container(border=True):
    st.markdown(
        '<span class="naglowek">Select tags</span><span class="wymagane">Required</span>',
        unsafe_allow_html=True,
    )

    szukaj = st.text_input(
        "Search tags",
        placeholder="Search tags...",
        icon=":material/search:",
        key=f"szukaj::{skey}",
        label_visibility="collapsed",
    )

    fraza = (szukaj or "").strip().lower()

    if fraza:
        pasujace = [t for t in ALL_TAGS if fraza in t.lower()]
        grupa_wybrane, grupa_recent = [], []
        grupa_reszta = pasujace
    else:
        pasujace = ALL_TAGS
        grupa_wybrane = [t for t in ALL_TAGS if t in selected]
        grupa_recent = [
            t
            for t, _ in sorted(st.session_state.uzycia.items(), key=lambda x: (-x[1], x[0]))
            if t not in selected
        ][:7]
        grupa_reszta = [t for t in ALL_TAGS if t not in selected and t not in grupa_recent]

    # Wszystkie pigułki żyją w jednym kontenerze i zawsze w tej samej kolejności w drzewie.
    # Grupowanie i przeskok zaznaczonych na górę robi wyłącznie CSS (własność order).
    # Przenoszenie przycisku między kontenerami gubiło pierwsze kliknięcie.
    kolejnosc_css = []
    for etykieta, klucz, grupa, order_naglowka in (
        ("✓ Selected", "hdr_wybrane", grupa_wybrane, 0),
        ("🕘 Recent Tags", "hdr_recent", grupa_recent, 2),
        ("🏷️ All Tags", "hdr_wszystkie", grupa_reszta, 4),
    ):
        widoczny = bool(grupa) and not (fraza and klucz != "hdr_wszystkie")
        if fraza and klucz == "hdr_wszystkie":
            widoczny = False
        # Nagłówek jest owinięty przez Streamlita w bezklasowy div i to on jest
        # elementem flexa, więc regułę trzeba nałożyć na rodzica przez :has().
        # Pigułki są bezpośrednimi dziećmi kontenera, więc dla nich :has() byłoby
        # błędem: trafiłoby w cały kontener.
        ukryj = "" if widoczny else " display: none;"
        kolejnosc_css.append(
            f'.st-key-{klucz}, div:has(> .st-key-{klucz}) '
            f'{{flex-basis: 100%; width: 100%; order: {order_naglowka};{ukryj}}}'
        )
        for nazwa in grupa:
            kolejnosc_css.append(
                f'.st-key-tag_{slug(nazwa)} {{order: {order_naglowka + 1};}}'
            )

    for nazwa in ALL_TAGS:
        if nazwa not in pasujace:
            kolejnosc_css.append(f'.st-key-tag_{slug(nazwa)} {{display: none;}}')

    for nazwa in selected:
        kolejnosc_css.append(
            f'.st-key-tag_{slug(nazwa)} button {{opacity: 1;'
            f' border-color: rgba(130,130,130,.85);'
            f' box-shadow: 0 0 0 2px rgba(130,130,130,.28);}}'
        )

    st.markdown("<style>" + "".join(kolejnosc_css) + "</style>", unsafe_allow_html=True)

    with st.container(horizontal=True, gap="small", key="pigulki"):
        for etykieta, klucz in (
            ("✓ Selected", "hdr_wybrane"),
            ("🕘 Recent Tags", "hdr_recent"),
            ("🏷️ All Tags", "hdr_wszystkie"),
        ):
            with st.container(key=klucz):
                st.markdown(f'<div class="sekcja">{etykieta}</div>', unsafe_allow_html=True)

        for nazwa in ALL_TAGS:
            st.button(
                nazwa,
                key=f"tag_{slug(nazwa)}",
                on_click=przelacz_tag,
                args=(skey, nazwa),
            )

    if not pasujace:
        st.caption("Brak tagów pasujących do wyszukiwania.")

# ------------------------------------------------------------------- akcje

lewa, wstecz, dalej = st.columns([2, 1, 1])

with lewa:
    if st.button("Sprawdź", type="primary", use_container_width=True):
        st.session_state.wyniki[skey] = set(selected)
        # Wynik odzwierciedla ostatnią odpowiedź, a nie najlepszą z dotychczasowych,
        # więc poprawienie dobrej odpowiedzi na złą odejmuje punkt.
        if selected == set(scenario["correct_tags"]):
            st.session_state.zaliczone.add(skey)
        else:
            st.session_state.zaliczone.discard(skey)

with wstecz:
    if st.button(
        "← Wstecz",
        use_container_width=True,
        disabled=indeks == 0,
        help="Wróć do poprzedniej rozmowy" if indeks else "To pierwsza rozmowa",
    ):
        st.session_state.indeks -= 1
        st.rerun()

with dalej:
    if st.button(
        "Od nowa" if ostatnie else "Dalej →",
        use_container_width=True,
        help="Wylosuj nową kolejność" if ostatnie else "Przejdź do kolejnej rozmowy",
    ):
        if ostatnie:
            nowa_runda()
        else:
            st.session_state.indeks += 1
        st.rerun()

# ---------------------------------------------------------------- informacja zwrotna

# Wynik jest zapamiętany osobno dla każdej rozmowy, żeby po cofnięciu się
# przyciskiem Wstecz nadal było widać ocenę i wyjaśnienie.
sprawdzone = st.session_state.wyniki.get(skey)

if sprawdzone is not None and sprawdzone == selected:
    zaznaczone = sprawdzone
    poprawne = set(scenario["correct_tags"])
    brakuje = sorted(poprawne - zaznaczone)
    nadmiar = sorted(zaznaczone - poprawne)

    status_twoj = derive_status(zaznaczone) or "bez zmiany statusu"
    status_wzor = derive_status(poprawne) or "bez zmiany statusu"

    linie = []
    if brakuje:
        linie.append("**Brakuje:** " + " ".join(f"`{t}`" for t in brakuje))
    if nadmiar:
        linie.append("**Do usunięcia:** " + " ".join(f"`{t}`" for t in nadmiar))
    if zaznaczone != poprawne:
        linie.append("**Powinno być:** " + " ".join(f"`{t}`" for t in sorted(poprawne)))
    linie.append(f"**Dlaczego:** {scenario['why']}")

    if zaznaczone == poprawne:
        linie.append(f"**W Salesforce zapisze się:** *{status_twoj}*")
    else:
        linie.append(
            f"**Z Twoich tagów zapisałoby się:** *{status_twoj}* &nbsp;·&nbsp; "
            f"a powinno *{status_wzor}*"
        )

    if zaznaczone == poprawne:
        st.success("Dokładnie tak.", icon="✅")
    elif not zaznaczone:
        st.warning("Nie zaznaczono żadnego tagu.", icon="⚠️")
    else:
        st.error("Jeszcze nie to.", icon="✏️")

    st.markdown("<br>".join(linie), unsafe_allow_html=True)

    if "Success" in zaznaczone and not any(t.startswith("Declared") for t in zaznaczone):
        st.warning(
            "Sam `Success` nic nie zapisze. Trzeba dołożyć tag `Declared ...`, "
            "żeby było wiadomo, co dokładnie się udało.",
            icon="🚨",
        )

    if ostatnie:
        st.divider()
        st.markdown(
            f"To była ostatnia rozmowa. Wynik rundy: "
            f"**{len(st.session_state.zaliczone)} / {len(SCENARIOS)}**."
        )
