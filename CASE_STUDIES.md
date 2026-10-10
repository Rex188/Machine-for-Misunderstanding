# Qualitative Case Studies: How the Medium Distorts Intentions
## Extended Phenomenological Logs & Dialogue Records

**Author**: Rex Li  
**Parent Report**: [A Machine for Misunderstanding: Laboratory Research Report](LAB_REPORT.md)  
**Project**: Portfolio Project 2 (`portfolio/project2/`)  
**Data Source**: `portfolio/project2/blind_test/data/`  

---

## Overview

This supplementary dossier documents two critical case studies from the formal double-blind experimental sessions. In both cases, the participants were placed in separate rooms, interacting solely through generative ambient sound modulated by real-time text input. These qualitative logs reveal how mediation systematically warps human intention, demonstrating that communicative distortion is not merely mathematical noise, but a visceral phenomenological reality.

---

## Case Study 1: The "Creepy Comfort" Paradox
**Session**: 6-Round Long-Horizon Evolution Test  
**Database**: `perf_20261003_111250.db`  
**Model Backend**: Local Qwen2.5-1.5B LoRA (MPS Accelerated)  

### Round 1: When Optimism Triggers Alarm
In Round 1, Participant A attempted to offer genuine encouragement to Participant B regarding gloomy weather:

- **Sender Input Text**: *"Your dream will come true."*
- **Sender Self-Reported VAD**: $V=0.63, A=0.40, D=0.93, C=0.67$ (High confidence, positive valence, calm energy)
- **Model Inferred VAD**: $V=0.75, A=0.60, D=0.80, C=0.43$
- **Receiver Acoustic Perception**: $V=0.07, A=0.80, D=0.20, C=0.14$
- **Receiver Qualitative Feedback**:  
  > *"Feel a sudden change in chords. A little scary and uncertain? And it's pretty fast."*
- **Calculated Deviations**:  
  - Model Gap ($d_{\text{model}}$): $0.154$
  - Medium Gap ($d_{\text{medium}}$): $0.536$
  - **Total Misunderstanding ($d_{\text{total}}$)**: $\mathbf{0.579}$

### Round 5: Amplified Reassurance, Deepened Alienation
By Round 5, sensing hesitation in the dialogue, Participant A attempted to double down on encouragement:

- **Sender Input Text**: *"You need to be confident!"*
- **Sender Self-Reported VAD**: $V=0.53, A=0.68, D=0.73, C=0.99$
- **Model Inferred VAD**: $V=0.50, A=0.70, D=0.60, C=0.48$
- **Receiver Acoustic Perception**: $V=0.14, A=0.30, D=0.23, C=0.26$
- **Receiver Qualitative Feedback**:  
  > *"He def wanna comfort me because the audio sounds deadass creepy. But that's not what I'm interpreting. Maybe he is confused."*
- **Calculated Deviations**:  
  - Model Gap ($d_{\text{model}}$): $0.078$
  - Medium Gap ($d_{\text{medium}}$): $0.377$
  - **Total Misunderstanding ($d_{\text{total}}$)**: $\mathbf{0.427}$

### Acoustic & Media Mechanism
1. **Algorithmic Inflation of Energy**: The language model associated "dreams" and "confidence" with high Arousal ($A = 0.60 - 0.70$) and high Dominance ($D = 0.60 - 0.80$).
2. **Voltage Transduction**: In our Eurorack mapping schema:
   - High Arousal pushed Channel 1 (`/vcv/timbre`) toward maximum, driving Plaits' 2-operator FM synthesis depth.
   - Channel 4 (`/vcv/envelope`) rapidly contracted, producing sharp, percussive transients.
3. **Psychoacoustic Inversion**: While the semantic meaning was benevolent, metallic FM overtones and high dissonance are culturally and evolutionarily coded as threat markers in human hearing. The medium violently inverted a gesture of warmth into a horror soundtrack.

---

## Case Study 2: Struggling for Mutual Grounding
**Session**: Formal Session 3  
**Database**: `perf_20261003_134304.db`  
**Model Backend**: Local Qwen2.5-1.5B LoRA (MPS Accelerated)  

This session captures a dynamic 4-round process where two participants progressively negotiated a shared protocol across acoustic turbulence.

### Round 0: The Coffee Tension
- **Sender Input Text**: *"I am expecting some coffee. I feel so happy to think about that we can have some coffee later."*
- **Sender Coordinates**: $V=0.93, A=0.73, D=1.00, C=0.61$
- **Receiver Coordinates**: $V=0.32, A=0.39, D=0.32, C=0.43$
- **Receiver Feedback**: *"I feel you are under much stress."*
- **Total Misunderstanding**: $\mathbf{0.563}$

### Round 1: Counter-Directional Guidance
- **Sender Input Text**: *"Make it soft and happier. Life is beautiful with a cup of coffee in hand."*
- **Sender Coordinates**: $V=0.66, A=0.71, D=0.68, C=0.72$
- **Receiver Coordinates**: $V=0.27, A=0.16, D=0.19, C=0.19$
- **Receiver Feedback**: *"Didn't change too much. Maybe she is frightened by this audio? I don't know but this sounds scary?"*
- **Total Misunderstanding**: $\mathbf{0.481}$

### Round 2: Explicit Textual Disambiguation
- **Sender Input Text**: *"Don't be sad and scared! I'm talking about coffee, which is very good and happy."*
- **Sender Coordinates**: $V=0.93, A=0.73, D=0.28, C=0.07$
- **Receiver Coordinates**: $V=0.48, A=0.48, D=0.45, C=0.54$
- **Receiver Feedback**: *"I feel you are calming down and thinking."*
- **Total Misunderstanding**: $\mathbf{0.313}$

### Round 3: Acoustic Convergence
- **Sender Input Text**: *"Add more beat and make it cheerful, happier."*
- **Sender Coordinates**: $V=0.74, A=0.79, D=0.79, C=0.80$
- **Receiver Coordinates**: $V=0.93, A=0.66, D=0.96, C=0.53$
- **Receiver Feedback**:  
  > *"Oh things are getting better!!!! Finally. I think she realized what I am talking about."*
- **Total Misunderstanding**: $\mathbf{0.165}$ (Lowest error across the session)

### Analytical Insight
Session 3 illustrates that communicative convergence is not passive transmission. Misunderstanding in early rounds forced the participants to actively calibrate their language. The sender shifted from describing internal mood ("I am expecting coffee") to issuing direct sonic instructions ("Add more beat and make it cheerful"), successfully steering the opaque medium toward mutual comprehension.
