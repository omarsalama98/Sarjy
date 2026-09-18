# How Physiotherapists Actually Reason: Research for a Voice AI Clinical Thinking Partner

*Research report — 18 September 2026*

---

## Summary

### The three things to act on

1. **Your first assumption is half wrong, and the half that's wrong is the important half.** Yes, in Egypt, Saudi Arabia and the UAE a physician referral is legally required. But in the UK, the US, the Netherlands and most of Western Europe, direct access is either the norm or the explicit policy direction. More importantly: **even when a referral exists, it usually doesn't contain a diagnosis.** One JOSPT study found only 32% of physician referral diagnoses were anatomically specific; a 2025 cross-sectional study found 33% of neck/back referrals arrived with *no* medical diagnosis at all, with "pain" as the stated reason in 88% of those. The physio is doing the diagnostic work in nearly every case — the referral label is a starting anchor, not an answer.

2. **Your second assumption is mostly wrong as stated, but points at something real.** Differential reasoning does *not* happen only after the appointment. The subjective exam **is** the differential — hypotheses form in the first minutes from the body chart, and the objective exam is explicitly designed as hypothesis *testing* (which tests you choose, and how hard you push, is determined by SINSS judgements made in the room). This is documented in the Jones/Edwards clinical reasoning literature and in think-aloud studies showing reflection-*in*-action during the encounter. **What genuinely happens after the session is different and narrower:** (a) documentation — 85% of US PTs report taking notes home; (b) reflection-*on*-action on the cases that didn't resolve cleanly; (c) the "what else could this be / did I miss something" re-check that new graduates describe carrying out of the room unresolved. Build for *that*, not for "the differential."

3. **Red flag screening is emphatically in physio scope — and physios are measurably bad at it unaided. This is your strongest product justification.** Austrian registered physiotherapists (n=479, 2024) correctly classified 79.4% of non-critical medical cases and 70.5% of MSK cases — but only **53.3% of critical medical cases**. A coin flip on the cases that kill people. The professional bodies (IFOMPT/JOSPT 2020, CSP, APTA) place this squarely in scope, and the UK's National Suspected Cauda Equina Pathway makes specific screening and documentation *mandatory* for physios regardless of who referred.

### The design consequences

| Finding | What it means for the product |
|---|---|
| Referral labels are non-specific or absent in ~1/3 to 2/3 of cases | The referral diagnosis is an **anchor to be challenged**, not context to be trusted. Surface it as a hypothesis with a confidence level, not as a fact. |
| Reasoning happens in-room; only *checking* happens after | The post-session slot is real but narrow. The highest-leverage untapped slot is the **pre-session brief for the next appointment** — physios see patients repeatedly and arrive cold. |
| Red flags have poor individual diagnostic accuracy (Downie, BMJ 2013) | **Do not build a checklist that fires alerts.** The current international framework explicitly rejects checklists in favour of an "index of suspicion" that accumulates across sessions. A checklist product would be professionally out of date on arrival. |
| Physios are the longitudinal contact; symptoms emerge between visits | Track red-flag signal **across the episode**, not per-visit. This is a capability nobody currently has and no scribe can produce. |
| 53.3% accuracy on critical medical cases | Challenge-the-reasoning is the value proposition, not documentation speed. |

### One external API — recommendation

**Europe PMC REST API.** Free, no API key, no rate-limit gate for normal use, covers 37.8M abstracts plus 3.2M open-access full texts, supports structured queries and returns citations with dates. Justification: the actual post-session physio question is *"is there evidence for X in this presentation"* / *"what's current on Y"*, and Europe PMC lets every claim the voice partner makes carry a real, checkable, dated reference. Runner-up considered and rejected: NICE Syndication API is free **only inside the UK** and charges territory-based licence fees overseas — a hard blocker if your physio is in Egypt or the Gulf. PEDro (the physiotherapy-specific evidence database, 70,000+ records) has **no public API that I could find** — verify directly with them before assuming otherwise.

Clinical prediction rules (Ottawa ankle, Canadian C-spine) should be **hardcoded, not API-called**: they are short, stable, public algorithms, and an API is the wrong shape for them.

### What I could not verify

- No national statistic exists (that I could find) for **what proportion of NHS MSK physiotherapy patients currently self-refer**. Policy commitment and service-level data exist; the headline number does not.
- **Egypt**: I found no primary regulatory document. The "no direct access" claim traces to secondary sources citing the General Physical Therapy Syndicate. Treat as probable but unconfirmed.
- **No physiotherapy-specific diagnostic error prevalence study exists.** The cognitive bias literature (anchoring, premature closure, diagnostic momentum) is imported from medicine. I found the concepts applied to physio qualitatively, never measured.
- Several key papers (JOSPT, Physiopedia, PubMed, ScienceDirect) blocked automated retrieval. Where I relied on search-engine summaries rather than primary text, I have flagged it inline as **[secondary]**.

---

## 1. The actual referral pathway

### The global picture

World Physiotherapy's **Annual Membership Census 2023** (published January 2024; 119 of 127 member organisations responding, 93.7% response rate) found that **35% reported full direct access** in their country or territory — people could see a physiotherapist without referral. That is the cleanest single global number available. It also means ~65% do not have full direct access, which is why your physio's intuition is grounded in something real.

But that global average conceals two completely different worlds.

### Where direct access is the norm or the trajectory

**United States.** As of **1 July 2025**, per APTA's *State of Direct Access to Physical Therapist Services* report, **all 50 states, DC and the US Virgin Islands have either provisional or unrestricted direct access** for evaluation and treatment — 21 states unrestricted, 29 plus DC and USVI provisional (time limits, visit caps, or referral requirements for specific procedures such as needle EMG). Note the important gap APTA itself flags: *legal* direct access ≠ *reimbursed* direct access. Payer policies still require referrals or prior authorisation in many cases, which is why utilisation lags legality.

Utilisation data: a large non-Medicare claims analysis of 62,707 outpatient PT episodes (Iowa and South Dakota) found **27% were self-referred** — over 17,000 self-referred versus over 45,000 physician-referred. Self-referred episodes used 86% of the visits and $0.87 for every $1.00 of physician-referred episodes. An earlier PTJ study (1997) found direct access episodes averaged **7.6 visits versus 12.2**, and **$1,004 versus $2,236**.

**United Kingdom.** Two separate mechanisms:
- *Private practice*: a chartered physiotherapist may treat a self-referring patient directly. No referral has ever been required. The CSP actively promotes self-referral as practice improvement.
- *NHS primary care*: **First Contact Physiotherapy (FCP)** embeds physios in general practice as the first clinician a patient sees, no GP consultation first. Funded via the Additional Roles Reimbursement Scheme (from 2019); the **NHS Long Term Plan committed to direct access to MSK FCPs for all adults in England by 2023/24**. The CSP estimates **85% of patients presenting to a GP with an MSK problem could be seen safely by a physiotherapist straight away**. MSK accounts for roughly 20–30% of all GP consultations.

The BJGP evaluation (Goodwin et al., *Br J Gen Pract* 2024;74(747):e717) — 426 adults across 46 UK general practices, December 2019 to October 2022 — found FCP patients re-consulted their GP for the same problem in **8.3%** of cases versus **30.9%** for those who started with the GP; fewer medications including opioids; lower NHS costs; and **"no safety issues were identified"** across any arm. That last finding matters for your product's positioning: the safety objection to physio-first has been tested and did not hold.

**European Union.** Bury & Stokes' review (*Physiotherapy*, 2013) found that in **over half of EU member states** service users can self-refer. Self-referral is the established norm in the Netherlands, Norway, Sweden and the UK. This is the most recent comprehensive EU mapping I could find — it is over a decade old, and the direction of travel since has been toward more access, not less.

### Where the "always referred" assumption is straightforwardly true

**Egypt.** Direct access is **not** permitted; patients require a referral. The profession is regulated by the General Physical Therapy Syndicate under Professional Practice Law No. 3 of 1985 and General Syndicate Law No. 209 of 1994; only graduates of physiotherapy faculties may practise. **[secondary — I could not obtain a primary regulatory text; treat as probable, not confirmed.]**

**Saudi Arabia.** Direct access is **not** allowed; all patients need a physician referral, and referrals sometimes specify which intervention to use. Physiotherapy is positioned as a secondary care service. Licensing is via the Saudi Commission for Health Specialties. A 2025 cross-sectional study of Saudi physiotherapists found **55.3% never or rarely consult a scope-of-practice document**, and only **24.7% correctly identified which practice settings permit direct access** — i.e. even the practitioners are unclear on their own boundaries.

**United Arab Emirates.** Direct access is not implemented in public health services (Alnaqbi, Shousha, AlKetbi & Hegazy, *PLOS ONE*, 11 June 2021; n=264). 70% of physiotherapists were aware of the concept, 30% had never heard of it. Barriers identified: limited physician and policymaker support, restricted autonomy, limited scope of practice, weak EBP infrastructure, and **concerns about diagnostic competence** — which is, notably, exactly the gap your product addresses.

### Verdict on assumption 1

> **Partially correct, geographically. Wrong in its implication.**

If your physio practises in Egypt or the Gulf, "patients arrive referred" is accurate. If they practise in the UK, US or most of Western Europe, it is increasingly false and getting falser.

But the implication — *"so the physio is not the one making the diagnosis"* — does not follow even where the referral is universal, for three independent reasons:

**(a) The referral usually contains no usable diagnosis.** Jette et al. (*JOSPT* 2005;35(9):572–579) found only **32%** of physician referral diagnoses to physical therapy were anatomically oriented and reported specific pathology. A 2025 cross-sectional study of neck and low back pain referrals found **33% arrived with no medical diagnosis at all**, with "pain" the stated reason in **88%** of those. The referral is an access token, not a diagnosis.

**(b) Physiotherapy diagnosis is a separate professional act.** APTA House of Delegates policy (**HOD P07-25-70-57, *Diagnosis by Physical Therapists***) states plainly that "physical therapists shall establish a diagnosis for each patient/client," and that PTs order diagnostic tests including imaging and labs where indicated. A companion policy (**HOD P06-15-25-24**) endorses movement system diagnostic labels distinct from pathoanatomic ones. The physio's diagnosis answers a different question from the doctor's: not *what is the tissue pathology* but *what is the movement dysfunction, what drives it, and what will change it*.

**(c) Where measured, physios diagnose at parity with physicians.** Pooled κ for diagnostic concordance between advanced practice physiotherapists and physicians is **0.76 (95% CI 0.68–0.85)** on moderate-certainty evidence. In an emergency department study, raw agreement was 86.1% with Gwet's AC1 = 0.84 (95% CI 0.69–0.98); a knee-disorder study found κ = 0.81 (95% CI 0.72–0.90); orthopaedic clinic studies report 74.5–90% agreement. The most common disagreement pattern: physios suspected fracture or contusion where the physician diagnosed a ligament or meniscal problem — i.e. physios erred toward caution.

**Design implication.** The referral diagnosis should enter your system as a **labelled prior with a confidence weight**, and the product should explicitly and routinely ask whether the findings support it. Treating the referral label as established context is the single most likely way to build anchoring bias into the tool.

---

## 2. What the physio actually does at a first appointment

The documented structure is stable across the English-speaking training tradition (Maitland-derived, taught essentially the same way in the UK, Australia, Ireland, and much of the Gulf and Egypt where curricula follow it).

### The subjective examination — canonical order

1. **Demographics, occupation, functional demands, patient's own goals**
2. **Body chart** — symptom distribution mapped on a body outline. Depth (deep/superficial), quality, constancy (constant vs intermittent), and presence of paraesthesia/numbness. Physiopedia's account is explicit that the body chart "should give the physiotherapist an initial impression (**working hypothesis**) as to which structures may be involved" — the differential starts here, in the first few minutes.
3. **Aggravating factors** — what activity/movement/position/posture provokes symptoms, *how long* it takes to provoke, and *how much* activity is required.
4. **Easing factors** — what relieves, and *how long* relief takes to arrive.
5. **24-hour behaviour (diurnal pattern)** — morning (including duration of morning stiffness — the key discriminator for inflammatory arthropathy), through the day, evening, night (night pain being a cardinal red flag).
6. **History of present condition** — onset (traumatic vs insidious), mechanism, progression, previous episodes, treatment to date and response.
7. **Past medical history, medications, imaging, special questions / red flags**
8. **Social history, yellow flags** (beliefs, fear-avoidance, work and compensation context)

### SINSS — the framework that governs everything downstream

**Severity, Irritability, Nature, Stage, Stability.** The authoritative modern treatment is Petersen EJ, Thurmond SM & Jensen GM, *"Severity, Irritability, Nature, Stage, and Stability (SINSS): A clinical perspective," Journal of Manual & Manipulative Therapy* 2021;29(5):297–309.

SINSS is **not** a documentation category. It is the decision function that determines **how much objective examination to perform and how hard to push**. Its stated purpose is to help the clinician "filter and group information, prioritise the problem list, and determine which tests should be used and when" — ensuring "the patient isn't under- or over-examined and/or treated" — and explicitly to **reduce clinical reasoning errors**.

- **Severity** — intensity of symptoms and the degree to which they limit activity.
- **Irritability** — Maitland's construct: *the ease with which symptoms are provoked and the time they take to settle.* Three characteristics govern classification: the time and vigour of activity required to aggravate; the severity of the pain produced; and the persistence of pain after the aggravating activity stops. Highly irritable = easily provoked, moderate-to-severe, slow to settle. The practical test is comparative: "pain goes immediately when I stand up straight" (low irritability) versus "pain persists 10–15 minutes after standing up straight" (high). Reliability of clinicians' irritability judgements has been formally studied in low back pain (*J Man Manip Ther*, 2009) and is imperfect — which is itself a reasoning-support opportunity.
- **Nature** — the clinician's hypothesis about the tissue/pathology/mechanism, including psychosocial contributors and precautions.
- **Stage** — acute / subacute / chronic.
- **Stability** — improving, worsening, or static. This is the variable most likely to change *between* sessions and the one your product is best placed to track.

The 2021 paper is candid that SINSS "has been inconsistently defined and applied in clinical practice" — which means a voice partner that applies it *consistently* is adding something real, not just formalising what already happens.

### The objective examination — hypothesis testing, not a protocol

Standard sequence: observation (posture, symmetry, atrophy/hypertrophy, signs of inflammation, gait) → active range of motion including functional tasks → passive physiological movement → overpressure → resisted/muscle testing → neurological screening (myotomes, dermatomes, reflexes) → special tests → palpation → accessory/joint play movements.

The critical point for your product: **which of these tests get performed, and in what order, and with how much force, is decided by the SINSS judgement made in the subjective.** A highly irritable presentation gets a truncated exam that stops before symptom reproduction. That decision is made *in the room*, in real time. This is why assumption 2 is wrong (see §4).

### Pain scales and outcome measures

- **NPRS** (Numeric Pain Rating Scale, 0–10) — the working default. MCID commonly cited as a **2-point reduction or 30% decrease**.
- **VAS** — 100mm line; largely superseded by NPRS in verbal/telehealth contexts because NPRS can be administered by voice.
- **PSFS** (Patient-Specific Functional Scale) — patient nominates 3–5 activities they can't do, rates each 0–10. Region-agnostic, exceptionally well-suited to voice capture.
- **Region-specific**: ODI (Oswestry Disability Index, low back — MCID commonly 8–10 points), NDI (neck), LEFS (lower extremity — MCID 9 points), UEFI / QuickDASH (upper limb), KOOS/HOOS (knee/hip), SPADI (shoulder).

**Licensing caution:** several of these are copyrighted instruments with restrictions on reproduction in commercial software. NPRS and PSFS are the safest to implement directly; check ODI and DASH licensing before embedding.

---

## 3. Red flag screening — is it genuinely in physio scope?

### Short answer: yes, unambiguously, and the referral does not discharge the duty

The definitive document is the **International Framework for Red Flags for Potential Serious Spinal Pathologies** — Finucane LM, Downie A, Mercer C, Greenhalgh SM, Boissonnault WG, Pool-Goudzwaard AL et al., *JOSPT* 2020;50(7):350–372. It was led by **IFOMPT** — the international federation of orthopaedic manipulative *physical therapists*. The profession wrote its own framework. Scope is not in question.

### The canonical MSK red flag categories

| Category | Representative features |
|---|---|
| **Cauda equina syndrome** | Bladder/bowel dysfunction, saddle anaesthesia, bilateral radicular pain, sexual dysfunction |
| **Fracture** | Significant trauma, osteoporosis, prolonged corticosteroid use, older age |
| **Malignancy** | Previous cancer history, unexplained weight loss, age >50, failure to improve with conservative care, night pain |
| **Infection** (spinal/septic arthritis) | Fever, IV drug use, immunosuppression, recent systemic infection, unremitting pain |
| **Inflammatory arthropathy** | Age <45 at onset, insidious onset, >30min morning stiffness, improvement with exercise not rest, night waking in second half of night, good NSAID response |
| **Vascular** (AAA, cervical arterial dysfunction) | Pulsatile mass, cardiovascular risk profile; for cervical — the "5 Ds and 3 Ns" |

### The crucial nuance: red flags perform badly individually

**Downie A et al., *BMJ* 2013 Dec 11;347:f7095** — systematic review of red flags to screen for fracture and malignancy in low back pain (14 studies). Findings:
- Only **13 red flags (25%)** had been evaluated in more than one study.
- Of the four red flags endorsed by the American College of Physicians guideline, only older age, trauma and corticosteroid use had any data — and **even when present, they raised the likelihood of fracture by up to only 15%**.

A 2025 scoping review on red flags for spinal malignancy reached similar conclusions about diagnostic utility.

**This is the single most important thing for your product to get right.** The 2020 international framework was written precisely because guidelines disagreed about which red flags to use, "which has led to confusion and inconsistency in clinical management." Its answer is not a better checklist — it is a **clinical reasoning pathway** in which red flags contribute to an evolving *index of suspicion*. Greenhalgh & Selfe's *Red Flags* pocketbooks (Elsevier) formalise the same idea with a **hierarchy of red flags**, an **index of suspicion**, explicit treatment of **"red herrings"**, and conditional probability reasoning.

**A voice AI that fires binary red-flag alerts would be building the exact artefact the profession spent a decade moving away from.** The correct model is cumulative suspicion across the episode.

### Yes — physios are the longitudinal safety net. This is documented.

This part of your framing is **correct and under-exploited**.

- Serious pathology "can develop between the physician consultation and the initial physical therapy evaluation" — the referral is a snapshot; the physio has the film.
- **Boissonnault WG & Ross MD, "Physical Therapists Referring Patients to Physicians: A Review of Case Reports and Series," *JOSPT* 2012;42(5):446–454** — identified **78 published case reports** of physical therapists referring patients to physicians with a subsequent medical diagnosis. Presenting symptoms: pain (n=60), weakness (n=4), tingling/numbness (n=2), combination (n=12).
- Documented example: a 48-year-old woman referred for low back pain who, **at the sixth session**, reported new left hand weakness and headaches — referred to the emergency department, diagnosed with lung cancer. The signal simply did not exist at session one. **[secondary — surfaced via search summary of the case report literature; verify the primary before citing publicly.]**
- Ross MD et al., *"Physical Therapist Clinical Reasoning and Action for Individuals With Undiagnosed Lower Extremity Tumors: A Report of 3 Cases," JOSPT* 2017 — three tumours found by physios during episodes of care.
- A vestibular therapist correctly identified stroke from vertebral artery dissection in a patient physicians had diagnosed as BPPV (*Diagnosis*, 2016 — "Diagnosis is a team sport").

The red-flag literature also names the mechanism by which the referring doctor's error propagates: **"diagnostic momentum, in which the initial diagnostic label given to the patient prohibits investigation of alternate possibilities downstream."** That is your product's adversary, stated by the profession in its own words.

### Professional body guidance

**CSP (UK).** The **National Suspected Cauda Equina Syndrome Pathway** (published February 2023; implications for physiotherapists set out by Williams JT, Lister H, Fakouri B & Panchmatia JR in *Physiotherapy*, March 2024;122(1)) imposes specific, non-optional obligations on physiotherapists:
- Screen for symptoms of **recent onset (<2 weeks)**: new difficulty initiating or impaired sensation of urinary flow; altered perianal/perineal/genital sensation; severe or progressive lower limb neurological deficit; loss of rectal fullness sensation; new sexual dysfunction.
- Sudden bilateral leg pain, or unilateral progressing to bilateral, requires urgent (<2 week) MSK referral.
- Document lower limb power and sensation. Digital rectal examination is **not** required in community/triage settings, but subjective perianal sensation assessment **is**.
- **"Negative examination findings do not exclude CES if positive subjective symptoms are present."**
- Safety-net with CES warning cards and videos for patient self-monitoring.
- Emergency referral on suspicion — and **"if a telephone assessment has taken place, it is not necessary to examine the patient face-to-face prior to making an emergency referral."**

The CSP also publishes *Learning from litigation: cauda equina syndrome* — a signal that this is where physios get sued. And CSP guidance confirms that **requesting plain X-ray, ultrasound and MRI is within physiotherapy scope**, with FCPs ideally holding the same referral rights as primary care colleagues.

**APTA (US).** Diagnosis, differential screening and referral are core scope (HOD P07-25-70-57). The JOSPT editorial *"Red Flags: To Screen or Not to Screen?"* (2010) states the duty directly: it is the physical therapist's responsibility to use a management model that evaluates red flag findings and triggers referral.

### The uncomfortable evidence: physios are not good at this unaided

This is your justification. It is strong and it is quantified.

| Study | Population | Result |
|---|---|---|
| Austrian registered physiotherapists, *BMC Primary Care* 2024 | n=479, clinical vignettes | **70.5%** MSK cases, **79.4%** non-critical medical, **53.3% critical medical** correctly classified |
| European final-year physiotherapy students, 15 countries (*Musculoskelet Sci Pract*, 2017) | undergraduate | mean **53%** (median 67%) of critical medical vignettes correct |
| Specific low back pain vignettes, 2026 | qualified physios | **47%** detection for lumbar spinal stenosis; **28%** for spondyloarthritis |
| French physiotherapists, self-referred patients (2023) | vignettes | management decisions outperformed diagnostic hypotheses, "especially for the critical medical category" |

A ~50% hit rate on the cases where being wrong causes catastrophic harm, in a profession where the practitioner sees the patient eight times and the doctor saw them once. That is the gap.

A 2025 feasibility study (*BMC Medical Education*) tested digital educational training to improve serious-pathology recognition — evidence the profession is actively looking for exactly this kind of intervention.

---

## 4. Clinical reasoning — during, and after

### Correcting assumption 2

> **"Differential reasoning happens AFTER the appointment, not in front of the patient."**
>
> **This is wrong as a description of clinical reasoning, and right as a description of workflow. The distinction matters enormously for what you build.**

**Why it's wrong.** The entire architecture of the physiotherapy assessment is built on in-room differential reasoning:

- Hypotheses are generated from the **body chart**, within minutes, and explicitly described in the teaching literature as the "working hypothesis."
- The **objective examination is hypothesis testing.** You do not run a fixed battery; you select tests to discriminate between the hypotheses you formed in the subjective. If differential reasoning happened afterwards, test selection would be impossible.
- **SINSS is an in-room reasoning act with immediate consequences** — it determines whether you stop the exam before reproducing symptoms.
- Physiotherapists in the MSK field are documented to use **"hypothetico-deductive reasoning and early hypothesis generation and testing"** in patient management (Jones).
- **Reflection-in-action** — Schön's term for real-time adjustment during the encounter — is documented empirically in physiotherapists. Gilliland S & Wainwright SF, *"Patterns of Clinical Reasoning in Physical Therapist Students," Physical Therapy* 2017;97(5):499–, used retrospective think-aloud after standardised patient encounters and found participants "frequently employed reflection-in-action during patient encounters."

Note the finding from that same study that maps directly onto your physio's self-report: four reasoning patterns emerged — **protocol-based**, hypothetico-deductive, pain reasoning, and behaviour analysis. Protocol-based reasoning (running a standard sequence, deferring interpretation) is a real and observed pattern — it is the *novice* pattern. A physio who says "I do the assessment, then think about it later" may be accurately describing a protocol-based workflow. That is a thing to support carefully, not a thing to design the whole product around as if it were expert practice.

**Why it's right anyway.** Three post-session activities are real, documented, and currently unsupported:

1. **Documentation, which genuinely happens later.** Per WebPT's *State of Rehab Therapy* 2024 **[secondary]**: 85% of physical therapists take documentation home; 36% name it a leading cause of burnout; only ~35% finish documentation during paid hours. Reported time: 8–15 minutes per encounter, 2–6 hours per day. Clinic norms vary from "notes done by end of day" to "clinicians documenting until 7pm."

2. **Reflection-on-action.** Schön's second category — looking back at what happened after the encounter. Distinct from reflection-in-action, and this is where the referral diagnosis gets genuinely reconsidered, where the non-responding patient gets rethought, and where literature gets looked up.

3. **Unresolved uncertainty carried out of the room.** Phua R, Mandrusiak A, Singh L, Martin R & Forbes R, *"Identifying and navigating suspected serious pathologies: New-graduate physiotherapists' perspectives and developmental needs," Musculoskeletal Science & Practice*, 2024 — 18 semi-structured interviews, reflexive thematic analysis. Four themes: (1) physiotherapists as advocates; (2) **navigating uncertainties and complexities**; (3) safe and accessible workplace support builds confidence; (4) importance of direct learning opportunities. New graduates recognise their role as first-contact practitioners "yet also experience significant uncertainties" — and resolve them, when they can, by finding a colleague afterwards.

**The product reframing.** Your voice partner is not capturing the differential — the physio already did that in the room. It is:
- the **colleague who isn't there** when the uncertainty gets carried out of the room (theme 3 above, stated as a developmental need by the profession itself);
- the thing that **challenges the anchor** the referral installed;
- the thing that **remembers across sessions** what a human clinician with a 40-patient caseload cannot.

And the strongest unclaimed slot is arguably not post-session at all: it's the **60-second pre-brief before the next appointment with the same patient**, where "last time you hypothesised X, stability was static, and you said you'd reassess Y" changes the encounter that is about to happen.

### The frameworks, named

**Hypothesis categories (Jones, 1987/1992, evolved since).** The set physiotherapists are taught to reason across:
- Pathobiological mechanisms (tissue healing stage, pain mechanisms — nociceptive / neuropathic / nociplastic)
- Source of symptoms / dysfunction
- Contributing factors
- Precautions and contraindications to examination and treatment
- Management / treatment
- Prognosis
- Functional limitations
- Patient perspectives on their experience

This is the natural ontology for your data model. It is what a physio's reasoning is already shaped like.

**Clinical reasoning strategies (Edwards I, Jones M, Carr J, Braunack-Mayer A, Jensen GM, *"Clinical Reasoning Strategies in Physical Therapy," Physical Therapy* 2004;84(4):312–330).** Multiple case study, grounded theory; 6 peer-designated expert physical therapists across orthopaedic, neurological and domiciliary practice plus 6 further expert interviews. The contribution is that physiotherapy reasoning is *not* one process. It identifies distinct strategies — diagnostic, narrative, procedural, interactive, collaborative, predictive, teaching and ethical reasoning — and the movement *between* them, which they term **"dialectical reasoning."**

> **Design consequence:** a tool that only supports *diagnostic* reasoning supports a minority of what a physio is doing. Narrative reasoning (understanding the patient's story and beliefs) and collaborative reasoning (shared decision-making) are co-equal strands, and they are where the physio's actual differentiator over an imaging report lives.

**Pattern recognition vs hypothetico-deductive.** Experts pattern-match; novices work hypothetico-deductively. Both are documented in physios. Patterns in physiotherapy exist "not only in classic diagnostic syndromes... but also in the pathobiological mechanisms associated with those syndromes and the multitude of environmental, physical, psychological, social and cultural factors." The failure mode of expert pattern recognition is exactly premature closure — which is what a reasoning partner exists to interrupt.

### How often does the referral label turn out to be wrong?

**I could not find a direct study of this, and I want to be explicit about it.** Nobody appears to have published "in N consecutive referred patients, the physiotherapist's diagnosis differed from the referral diagnosis in X%." If that study exists it did not surface across a dozen searches.

What can be said from adjacent evidence:
- In **32–67%** of cases, the question is moot because the referral carries no specific diagnosis to disagree with (Jette 2005; 2025 cross-sectional study).
- Where both parties commit to a specific diagnosis, agreement is **good to very good** (κ ≈ 0.76–0.84) — but those studies used advanced-practice physios in ED and orthopaedic triage, not community physios receiving specialist referrals.
- The disagreements that do occur cluster around fracture/contusion versus soft tissue.

**This is a genuine research gap and arguably a data asset you could build.** A product that records the referral label and the physio's post-assessment formulation generates precisely the dataset that does not currently exist.

---

## 5. What physios actually look up, and what has a usable API

### What gets looked up

**Clinical prediction rules** — used to decide whether imaging or onward referral is needed:
- **Ottawa Ankle Rules** — ankle X-ray if tenderness over posterior 6cm or tip of lateral/medial malleolus; midfoot X-ray if tenderness over navicular or base of 5th metatarsal; imaging if unable to take four steps both immediately and at assessment. Sensitivity approaching 100%, modest specificity; reduces unnecessary radiographs by **30–40%**. One survey found **48% of physiotherapists used them intentionally** **[secondary — provenance uncertain]**.
- **Ottawa Knee Rule**, **Canadian C-Spine Rule** (clears cervical spine without imaging in alert, stable trauma patients), **Wells criteria** (DVT), **Canadian CT Head Rule**.
- Condition-specific CPRs: lumbar spinal stenosis, cervical radiculopathy (Wainner), carpal tunnel.

**Guidelines** — NICE (UK), JOSPT/APTA Academy of Orthopaedic Physical Therapy ICF-linked CPGs (Low Back Pain rev. 2021, Neck Pain rev. 2017, and regional guidelines), national MSK pathways.

**Outcome measures and their MCIDs** — see §2.

**Exercise prescription** — HEP libraries (Physitrack, Medbridge, PhysioTools), dosage parameters, progression criteria.

**Evidence** — PEDro (physiotherapy-specific, 70,000+ trials, reviews and guidelines, run by the Institute for Musculoskeletal Health at University of Sydney), PubMed, Cochrane.

### API assessment

| Source | API? | Free? | Verdict |
|---|---|---|---|
| **Europe PMC** | Yes — Articles REST API, Annotations API, Grants API, OAI, SOAP | Yes. No key mentioned; open-access content and metadata. 37.8M abstracts, 6.4M full-text records, 3.2M OA items | **Recommended.** Only restriction: no bulk automated download of non-OA content |
| **NICE Syndication API** | Yes — REST, JSON/XML, all NICE guidance, quality standards and public information | **Free within the UK only.** Overseas use incurs territory-based licence fees; 3-month test licences available; apply to syndication@nice.org.uk | Strong content, wrong economics if the user is outside the UK. Keep as a UK-market upgrade path |
| **WHO ICD-11 API** | Yes — REST, cloud-hosted at id.who.int, also self-hostable | Yes. CC BY-ND 3.0 IGO | Useful for coding/terminology normalisation, not for reasoning |
| **PEDro** | **None found** | Database is free to use | The obvious physio-specific source has no discoverable programmatic access. **Verify directly with PEDro before ruling out** |
| **MDCalc** | **No public API found** | — | Hosts Ottawa/Canadian rules as calculators; no documented developer access |
| **JOSPT CPGs** | No | Some CPG PDFs are freely mirrored by the Academy of Orthopaedic Physical Therapy (orthopt.org) | PDFs, not machine-readable |
| **wger** | Yes — REST, no authentication required for the exercise DB | Yes. AGPLv3 code; exercise/ingredient data CC BY-SA 3.0. ~845+ exercises with multilingual names, muscle groups, equipment, images | Viable for exercise prescription, but it is a *fitness* database, not a rehab one. Dosage and progression logic for pathology is absent |

### Recommendation and justification

**Europe PMC REST API.**

The justification is not "it's free" — it's that it matches the shape of the actual post-session question. When a physio sits down after a session and thinks *"this doesn't fit the referral label"* or *"is this presentation actually consistent with X"*, the resolution step is literature, and it is literature they will not go and find because it takes twenty minutes they do not have. Europe PMC turns that into a sub-second call, returns dated citations, and — critically for a clinical tool — lets every assertion the voice partner makes be **attributed and checkable**. An unattributed LLM claim in a clinical reasoning context is a liability; a claim with a PMID and a date is a conversation.

Secondary justification: it covers PEDro's underlying primary literature even though PEDro itself is closed, so you get most of the physiotherapy evidence base by another route.

**Hardcode, don't API:** Ottawa Ankle/Knee, Canadian C-Spine, and the red flag constellations. These are short, stable, publicly documented algorithms. Calling out to a third party for them adds latency and a failure mode for no benefit — and for a voice product, latency is the product.

---

## 6. Known reasoning failure modes

### What the physio literature names explicitly

- **Anchoring on the referral diagnosis / diagnostic momentum.** Named directly in the physiotherapy red-flag literature: "delayed or missed diagnoses may be partly attributable to diagnostic momentum, in which the initial diagnostic label given to the patient prohibits investigation of alternate possibilities downstream." In physiotherapy this is structurally worse than in medicine, because the referral label arrives *before* the clinician forms any independent impression, and arrives with the authority of a specialist.
- **Premature closure** — accepting a diagnosis before it is fully verified. In general medicine, self-reported by 58.5% of physicians in a Japanese survey; anchoring by 60.0%; availability bias 46.2%. The expert physio's reliance on pattern recognition is precisely the cognitive machinery that produces it.
- **Search satisficing** — stopping once a plausible mechanical explanation is found. The red-flag framing literature's core worry: "treating an undetected serious condition as if it were mechanical is precisely what screening exists to prevent."
- **Confirmation bias in the objective exam** — a physio who hypothesises impingement selects impingement tests. Test selection is hypothesis-driven by design, which makes it hypothesis-confirming by default.
- **Low base rate desensitisation.** Serious pathology is rare in MSK caseloads. Rarity plus poor individual red flag accuracy plus repeated non-events produces reasonable-feeling complacency. The Austrian 53.3% figure is what this looks like measured.
- **Inconsistent application of the structure that exists.** The 2021 SINSS paper: the construct "has been inconsistently defined and applied in clinical practice."

### What I could not find

**There is no published prevalence study of diagnostic error in physiotherapy specifically.** The general figures (diagnostic error affects ~5% of US outpatient adults, ~12 million annually; a 2024 cross-sectional estimate of 2.59 million missed diagnoses causing 795,000 serious harms; cognitive factors contributing to ~74% of diagnostic errors) are from medicine and cannot be transferred without caveat. The physiotherapy evidence is: vignette studies of accuracy (§3), case-report series of catches (§3), and qualitative studies of uncertainty (§4). **Nobody has measured how often physios get it wrong in real practice.** Be honest about that in any marketing claim.

---

## 7. Existing products

### Directly adjacent

**Physiotutors Clinical Assistant ("ChatCPG") + AI Co-Pilot** — the closest thing to your concept that exists. ChatCPG is a chat assistant grounded in international clinical practice guidelines, marketed as "a mentor in your pocket," 50+ languages, free 14-day trial then bundled with premium membership. Separately, an **AI Co-Pilot that "listens, transcribes, and gives quick access to relevant, evidence-based information during every patient session"** — i.e. they are already in the voice, in-session space. Their own caveat: "the AI can still make mistakes" and it "should complement, not replace, clinical judgment."
*What it misses:* it is a question-answering tool. It has no memory of the patient across sessions, no model of the referral anchor, no SINSS state, and no mechanism for challenging the clinician's reasoning unprompted. It answers what you ask. It does not ask what you didn't.

**Flok Health (Cambridge, UK)** — the notable outlier: not a clinician tool but an autonomous AI physiotherapist. Certified as a **Class IIa medical device** (reported October 2025), described as the first AI system approved in the UK or Europe to autonomously deliver end-to-end diagnostic triage and treatment without clinician input. Pilot at Cambridgeshire Community Services NHS Trust, **February–June 2025** (12 weeks): more than halved back pain waiting lists and reduced MSK waits by 44%. Raised **$12.5M Series A**; expanded regulatory clearance across MSK and pelvic health pathways.
*Strategically important:* Flok is competing for the *patient*, not the clinician. It validates regulatory feasibility and it is the argument your physio will hear ("won't AI replace me?"). Your positioning is the opposite bet — augment the clinician's judgement rather than substitute it.

### AI scribes serving physiotherapy

Heidi Health, PatientNotes (CEO Darren Ross is himself a physiotherapist), Nabla, Dorascribe, Skriber, Tandem Health, DeepCura. All documentation-first: transcribe the encounter, generate a SOAP note. Reported 50–75% documentation time reduction.

**The documented gap is precisely your thesis.** A 2025 analysis of AI scribe end-user feedback (arXiv 2512.04118) found clinicians flagging **"the lack of appropriate clinical reasoning in AI scribe outputs... as a critical limitation that could negatively impact clinical outcomes,"** alongside hallucinated diagnoses, exam findings, symptoms, dates and medications. PatientNotes has publicly signalled interest in moving toward suggesting exercise prescriptions and "even guide clinical reasoning" — so this space will be contested, from the documentation side inward.

### Physician-side reasoning tools (the pattern to learn from, not compete with)

**Glass Health** — combines ambient scribing with clinical decision support so the encounter that generates the note also generates the differential and assessment plan. **Microsoft Dragon Copilot** (launched March 2025) — unified voice AI assistant for documentation, information surfacing and task automation; ~5 minutes saved per encounter, reduced burnout in 70% of surveyed clinicians. **Penda Health / OpenAI** — LLM clinical copilot offering clinicians a second opinion on demand.

None of these are built for physiotherapy, and the mismatch is structural, not cosmetic: they assume a single diagnostic encounter, a pathoanatomic diagnosis, and no repeated longitudinal contact. Physiotherapy is 6–12 sessions over 8 weeks with a movement-system formulation that evolves. That is a different product.

### The unoccupied ground

Nothing found does any of the following:

1. **Treats the referral diagnosis as an anchor to be actively challenged**, with the physio's independent formulation recorded separately.
2. **Tracks red flag signal cumulatively across an episode of care** as an index of suspicion rather than per-visit checklist — the model the 2020 international framework actually calls for.
3. **Maintains SINSS state across sessions**, particularly Stability (improving/static/worsening), and flags when the trajectory contradicts the working hypothesis.
4. **Briefs the clinician before the next session** rather than only debriefing after the last one.
5. **Interrupts premature closure by asking what was ruled out and how** — the thing the supervising colleague does, which new graduates explicitly named as their developmental need.

---

## Sources

**Referral pathways and direct access**
- [APTA — State of Direct Access to Physical Therapist Services (July 2025)](https://www.apta.org/apta-and-you/news-publications/reports/2025/state-of-direct-access-to-physical-therapist-services) · [full PDF](https://www.apta.org/contentassets/6f37221cc8cc4087ab79aaf206d8dee8/apta-state-of-direct-access-2025-final-1.pdf)
- [APTA — Direct Access by State](https://www.apta.org/advocacy/issues/direct-access-advocacy/direct-access-by-state)
- [World Physiotherapy — Annual Membership Census 2023, global report (Jan 2024)](https://world.physio/sites/default/files/2024-01/AMC2023-Global.pdf) · [Policy statement: direct access and self-referral (2023)](https://world.physio/sites/default/files/2024-01/PS-2023-Direct-access.pdf)
- [Bury & Stokes — Direct access and self-referral to physiotherapy in the EU, *Physiotherapy* 2013](https://pubmed.ncbi.nlm.nih.gov/23537881/)
- [NHS England — First contact physiotherapists](https://www.england.nhs.uk/gp/expanding-our-workforce/first-contact-physiotherapists/)
- [First contact physiotherapy: clinical effectiveness and costs, *BJGP* 2024;74(747):e717](https://bjgp.org/content/74/747/e717) · [PMC full text](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11325442/)
- [Comparison of health care use for physician-referred vs self-referred outpatient PT episodes (2012)](https://pubmed.ncbi.nlm.nih.gov/22092033/)
- [Resource use and cost in direct access vs physician referral PT episodes, *PTJ* 1997](https://academic.oup.com/ptj/article-abstract/77/1/10/2633027)
- [Alnaqbi et al. — Barriers to direct access in the UAE, *PLOS ONE*, 11 June 2021](https://journals.plos.org/plosone/article?id=10.1371%2Fjournal.pone.0253155)
- [Physiotherapists' perspectives on direct access in Saudi Arabia (2025)](https://pubmed.ncbi.nlm.nih.gov/39922593/) · [Implementation of direct access policy in Saudi Arabia, *RMHP*](https://pmc.ncbi.nlm.nih.gov/articles/PMC13555331/)
- [The chaos of physiotherapy in Egypt — unlicensed centres (Zawia3)](https://zawia3.com/en/physical-therapy-chaos/)
- [CSP — self-referral, key implementation considerations](https://www.csp.org.uk/documents/key-considerations-implementation-self-referral)

**Referral diagnosis quality and diagnostic concordance**
- [Jette et al. — Current status and correlates of physicians' referral diagnoses for physical therapy, *JOSPT* 2005;35(9):572-9](https://pubmed.ncbi.nlm.nih.gov/16268244/)
- [Physician referrals for neck and low back pain to physical therapy: cross-sectional study (2025)](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11970003/)
- [Diagnostic concordance between physiotherapists and emergency physicians (2024)](https://pmc.ncbi.nlm.nih.gov/articles/PMC11584553/)
- [Concordance between physiotherapists and physicians in the ED, *BMC Emerg Med* 2019](https://pmc.ncbi.nlm.nih.gov/articles/PMC6842540/)
- [Diagnostic validity and triage concordance for common knee disorders, *BMC Musculoskelet Disord* 2017](https://link.springer.com/article/10.1186/s12891-017-1799-3)
- [APTA — Diagnosis by Physical Therapists (HOD P07-25-70-57)](https://www.apta.org/apta-and-you/leadership-and-governance/policies/diagnosis-by-physical-therapist) · [Movement System Diagnosis](https://www.apta.org/patient-care/interventions/movement-system-management/movement-system-diagnosis)

**Assessment structure, SINSS, outcome measures**
- [Petersen, Thurmond & Jensen — SINSS: A clinical perspective, *J Man Manip Ther* 2021;29(5):297-309](https://pubmed.ncbi.nlm.nih.gov/33999785/) · [record](https://scholarworks.bgsu.edu/physical_therapy_pub/4/)
- [Physiopedia — SINSS](https://www.physio-pedia.com/Severity,_Irritability,_Nature,_Stage_and_Stability_(SINSS))
- [An Exploration of Maitland's Concept of Pain Irritability in Low Back Pain (2009)](https://pmc.ncbi.nlm.nih.gov/articles/PMC2813500/) · [Reliability of Maitland's irritability judgments](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC2762835/)
- [Physiotherapy Assessment / Subjective (Wikibooks)](https://en.wikibooks.org/wiki/Physiotherapy_Assessment/Subjective)
- [Physiopedia — Clinical Examination template](https://www.physio-pedia.com/Template:Clinical_Examination)
- [Minimum important differences for the PSFS, 4 region-specific measures, and the NPRS (2014)](https://pubmed.ncbi.nlm.nih.gov/24828475/)

**Red flags and serious pathology**
- [Finucane et al. — International Framework for Red Flags for Potential Serious Spinal Pathologies, *JOSPT* 2020;50(7):350-372](https://pubmed.ncbi.nlm.nih.gov/32438853/) · [journal page](https://www.jospt.org/doi/10.2519/jospt.2020.9971)
- [Downie et al. — Red flags to screen for malignancy and fracture in low back pain, *BMJ* 2013;347:f7095](https://pmc.ncbi.nlm.nih.gov/articles/PMC3898572/)
- [Diagnostic utility of red flags for spinal malignancy: scoping review (2025)](https://www.mdpi.com/2077-0383/14/20/7174)
- [Williams, Lister, Fakouri & Panchmatia — The National Suspected Cauda Equina Syndrome Pathway: implications for physiotherapists, *Physiotherapy*, March 2024](https://www.csp.org.uk/journal/article/physiotherapy-journal-march-2024/national-suspected-cauda-equina-syndrome-pathway)
- [CSP — Learning from litigation: cauda equina syndrome](https://www.csp.org.uk/publications/learning-litigation-cauda-equina-syndrome-ces)
- [Greenhalgh & Selfe — *Red Flags: A Guide to Identifying Serious Pathology of the Spine* (Elsevier)](https://shop.elsevier.com/books/red-flags/greenhalgh/978-0-443-10140-3)
- [Boissonnault & Ross — Physical Therapists Referring Patients to Physicians: A Review of Case Reports and Series, *JOSPT* 2012;42(5):446-454](https://pubmed.ncbi.nlm.nih.gov/22282166/)
- [PT Clinical Reasoning and Action for Individuals With Undiagnosed Lower Extremity Tumors, *JOSPT* 2017](https://www.jospt.org/doi/10.2519/jospt.2017.7037)
- [Red Flags: To Screen or Not to Screen?, *JOSPT* 2010](https://www.jospt.org/doi/10.2519/jospt.2010.0109)
- [Diagnosis is a team sport — vestibular therapist and dizziness (2016)](https://pmc.ncbi.nlm.nih.gov/articles/PMC5532056/)
- [The ability of Austrian registered physiotherapists to recognise serious pathology, *BMC Primary Care* 2024](https://link.springer.com/article/10.1186/s12875-024-02634-8) · [PMC](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11523903/)
- [Keep/refer decision making of European final-year physiotherapy students (2017)](https://www.researchgate.net/publication/321378961_Keeprefer_decision_making_abilities_of_European_final_year_undergraduate_physiotherapy_students_a_cross-sectional_survey_using_clinical_vignettes)
- [French physiotherapists' diagnostic hypotheses and management decisions for self-referred patients (2023)](https://pubmed.ncbi.nlm.nih.gov/37902190/)
- [Physiotherapists' ability to identify and manage specific low back pain: vignette study (2026)](https://www.sciencedirect.com/science/article/abs/pii/S2468781226001049)
- [Improving physiotherapists' ability to recognise serious pathology with digital training, *BMC Med Educ* 2025](https://link.springer.com/article/10.1186/s12909-025-08101-x)
- [CSP — First contact physiotherapy radiology guidance](https://www.csp.org.uk/professional-clinical/improvement-innovation/first-contact-physiotherapy/first-contact-physio-0)

**Clinical reasoning**
- [Edwards, Jones et al. — Clinical Reasoning Strategies in Physical Therapy, *Physical Therapy* 2004;84(4):312-330](https://academic.oup.com/ptj/article/84/4/312/2805347)
- [Gilliland & Wainwright — Patterns of Clinical Reasoning in Physical Therapist Students, *Physical Therapy* 2017;97(5):499-](https://academic.oup.com/ptj/article/97/5/499/3089730)
- [Phua, Mandrusiak, Singh, Martin & Forbes — Identifying and navigating suspected serious pathologies: new-graduate physiotherapists' perspectives and developmental needs, *Musculoskelet Sci Pract* 2024](https://pubmed.ncbi.nlm.nih.gov/38520877/)
- [Physiopedia — Clinical Reasoning for Musculoskeletal Practice](https://www.physio-pedia.com/Clinical_Reasoning)
- [Clinical reasoning in physiotherapy (Basicmedical Key — Jones hypothesis categories)](https://basicmedicalkey.com/clinical-reasoning-in-physiotherapy/)
- [Premature Closure: Anchoring Bias, Diagnosis Momentum, Search Satisficing (Springer, 2019)](https://link.springer.com/chapter/10.1007/978-3-319-93224-8_23)
- [Cognitive bias and diagnostic errors among physicians in Japan: self-reflection survey (2022)](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9032995/)
- [Writing for the role: new graduate physiotherapists' transition to clinical documentation (2024)](https://www.tandfonline.com/doi/full/10.1080/09593985.2024.2315255)

**APIs and evidence sources**
- [Europe PMC — Developers](https://dev.europepmc.org/developers)
- [NICE syndication API](https://www.nice.org.uk/reusing-our-content/nice-syndication-api) · [syndication and API guide](https://www.nice.org.uk/corporate/ecd10)
- [WHO ICD-11 API documentation](https://icd.who.int/docs/icd-api/APIDoc-Version2) · [licence](https://icd.who.int/docs/icd-api/license/)
- [PEDro — Physiotherapy Evidence Database](https://pedro.org.au/)
- [wger — open source fitness/exercise database with REST API (GitHub)](https://github.com/wger-project/wger) · [docs](https://wger.readthedocs.io/)
- [MDCalc — Ottawa Ankle Rule](https://www.mdcalc.com/calc/1670/ottawa-ankle-rule) · [Canadian C-Spine Rule](https://www.mdcalc.com/calc/696/canadian-c-spine-rule)
- [APTA — Ottawa Ankle Rules test & measure](https://www.apta.org/patient-care/evidence-based-practice-resources/test-measures/ottawa-ankle-rules-oar)
- [JOSPT — Interventions for Acute and Chronic Low Back Pain: Revision 2021 (ICF-linked CPG)](https://www.jospt.org/doi/10.2519/jospt.2021.0304)

**Existing products**
- [Physiotutors Clinical Assistant / ChatCPG](https://www.physiotutors.com/tools/clinical-assistant/)
- [AI physiotherapist approved to make autonomous decisions — Digital Health, October 2025](https://www.digitalhealth.net/2025/10/ai-powered-physiotherapist-approved-to-make-autonomous-decisions/)
- [Flok Health raises $12.5M Series A](https://thenextweb.com/news/flok-health-12-5m-series-a-ai-physiotherapist) · [Flok Health](https://www.flok.health/)
- [Patient Safety Risks from AI Scribes: Signals from End-User Feedback (arXiv 2512.04118)](https://arxiv.org/pdf/2512.04118)
- [Heidi Health — AI medical scribe for physiotherapists](https://www.heidihealth.com/en-ca/use-case/physio) · [PatientNotes](https://www.patientnotes.app/professions/physiotherapist)
- [Glass Health — clinical decision support and differential generation](https://glass.health/resources/medical-ai-tools)
- [Microsoft Dragon Copilot launch, March 2025](https://news.microsoft.com/source/2025/03/03/microsoft-dragon-copilot-provides-the-healthcare-industrys-first-unified-voice-ai-assistant-that-enables-clinicians-to-streamline-clinical-documentation-surface-information-and-automate-task/)
- [AI-Powered Physiotherapy: Evaluating LLMs Against Students in Clinical Rehabilitation Scenarios (2026)](https://doi.org/10.3390/app16031165)
- [Usefulness of ChatGPT in physiotherapy practice: a scoping review](https://www.sciencedirect.com/science/article/pii/S0031940626004633)
- [Reduce after-hours documentation in physical therapy (WebPT State of Rehab Therapy 2024 figures, secondary)](https://ac-health.com/reduce-after-hours-documentation-in-physical-therapy/)
