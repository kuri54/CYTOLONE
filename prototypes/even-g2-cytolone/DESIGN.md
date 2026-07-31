# CYTOLONE Hands-Free Workflow Design Lock

Status: approved for prototype implementation  
Target: purchase-presentation prototype using the official Even Hub Simulator  
Branch: `feature/even-g2-prototype`

## 1. Objective

Replace only the unpurchased Even G2 and R1 hardware with the official simulator. The image input and CLIP inference must remain the real CYTOLONE workflow.

```text
Microscope + C-mount iPhone / imported demo image
                         |
                         v
               CYTOLONE on the Mac
             real CLIP ViT-B/16 inference
                         |
                         v
             official Even Hub Simulator
                G2 display + R1 input
```

The purchase demo uses an image imported into the current CYTOLONE screen. The intended hardware workflow later replaces the Mac Analyze-button press with an R1 click while preserving capture of the current iPhone frame.

## 2. Fixed Product Behavior

### 2.1 Mac UI

Add an external-output selector to CYTOLONE Main:

```text
External output
- None
- Even G2
```

- The Mac result remains visible in both modes.
- `None` is the safe startup default.
- G2 result delivery and G2/R1 commands are enabled only for `Even G2`.
- The selector is an external-output extension point. Only `None` and `Even G2` are implemented in this prototype.
- Show G2 connection state: disabled, waiting, connected, or error.

Add a specimen selector to CYTOLONE Main. The prototype exposes only `Cervix`; the list must come from the Mac so `Urine` can be added later without hard-coding a second G2 workflow.

### 2.2 Question Types

G2 exposes:

- Anomaly
- Malignancy
- Bethesda
- Diagnosis

`Full` remains available on the existing Mac UI but is not selectable on G2.

G2 specimen and question-type selections update the corresponding Mac controls. Mac changes also update G2. The Mac is the source of truth when reconnecting.

### 2.3 Analyze Trigger

All triggers must converge on the existing CYTOLONE capture and inference semantics:

- Existing Mac Analyze button
- Simulator input representing R1 click
- Future foot pedal

For an imported-image demo, R1 analysis uses the image already loaded into CYTOLONE. When a live iPhone camera is active, an R1 command first captures the current browser video frame using the same center-crop semantics as the Mac Analyze button. A stale cached camera frame must never take priority over the live frame.

### 2.4 G2 Result

Send classification output only:

- Specimen
- Question type
- Every label for that question type, sorted by descending probability
- Percentage for every label

The first view must expose at least the top three. Remaining labels may be reached by scrolling if they do not fit simultaneously.

If a platform limit prevents all labels from being displayed, fall back to top three. Do not silently fall back below top three.

Never send any of the following to G2:

- LLM comments
- Differential findings
- Clinical information
- Suggested additional tests
- Patient identifiers

When LLM generation is enabled, publish CLIP results to G2 as soon as classification finishes. G2 must not wait for LLM generation. Mac-only LLM behavior remains unchanged.

### 2.5 G2 / R1 Interaction

Idle screen:

```text
CYTOLONE

> ANALYZE
  SPECIMEN: CERVIX
  MODE: BETHESDA
```

- Up / Down: move between items or scroll results
- Click on `ANALYZE`: request inference
- Click on `SPECIMEN`: open the specimen candidate list
- Click on `MODE`: open the G2-supported question-type candidate list
- Up / Down in a candidate list: move the selection
- Click in a candidate list: confirm the selected value and return to idle
- Double click: cancel a candidate list or return from a result to idle

Inference states:

- Ready
- Queued
- Analyzing
- Result
- Error (`NO IMAGE`, `CONNECTION LOST`, or `INFERENCE ERROR`)

## 3. Prototype Communication

The official Simulator and CYTOLONE run on the same Mac. A local hands-free bridge carries:

- G2 heartbeat and connection state
- Specimen and question-type synchronization
- Analyze commands
- Classification results
- Short machine-readable error states

The first prototype binds this bridge to localhost. A real G2 runs through a phone, so LAN binding, pairing, and authentication are separate post-purchase work and must not be claimed as validated by this demo.

## 4. Demo Script

1. Start CYTOLONE and the official Even Hub Simulator.
2. Open CYTOLONE Main.
3. Import an existing cytology image.
4. Set External output to `Even G2`.
5. Confirm `Cervix` and select a supported question type on G2.
6. Use the Simulator Click action on `ANALYZE`.
7. Confirm real CLIP ViT-B/16 inference runs on the Mac.
8. Confirm the same classification appears on the Mac and G2.
9. Confirm the G2 result contains sorted labels and percentages, with at least top three immediately accessible.
10. If LLM is enabled, confirm comments appear only on the Mac.

## 5. Acceptance Criteria

- The existing Mac Analyze button still produces the same classification behavior.
- An imported image can be analyzed without pressing the Mac Analyze button.
- With a live iPhone camera, each G2 Analyze captures and classifies the frame visible at that moment.
- G2 and Mac specimen/question controls remain synchronized.
- `Full` remains on Mac and never appears as a G2 selection.
- `None` prevents result delivery and rejects G2 analyze commands.
- `Even G2` publishes classification results and accepts Simulator input.
- Every available classification label and percentage is sent in descending probability order.
- G2 never receives an LLM-generated field.
- G2 receives the CLIP result before optional Mac-only LLM completion.
- Simulator Up, Down, Click, and Double click complete one workflow.
- Type/build checks and automated bridge tests pass.

## 6. Explicit Non-Goals

- Real G2/R1 Bluetooth behavior
- Real-device optical visibility at the microscope
- Foot-pedal implementation in the purchase demo
- Urine model or urine labels
- iPhone standalone inference
- Authenticated Mac-to-phone LAN transport
- G2 display of LLM output

The future foot pedal must call the same Analyze command rather than introduce a second inference path.
