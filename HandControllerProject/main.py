import cv2
import mediapipe as mp
import math
import numpy as np
import pyautogui
import time

# --- CONFIGURATION ---
pyautogui.FAILSAFE = False # Prevent random crashes from corner hits
pyautogui.PAUSE = 0
LETTERS = " ABCDEFGHIJKLMNOPQRSTUVWXYZ"
SYMBOLS = "1234567890.,!?;:@#&+-/*="
MOUSE_SENS = 1500  # Lowered slightly for better control
DIAL_SMOOTHING = 0.2 
PINCH_T = 0.06 # More forgiving distance for "joined" fingers

# Initialize MediaPipe
mp_hands = mp.solutions.hands
hands = mp_hands.Hands(max_num_hands=2, min_detection_confidence=0.8, min_tracking_confidence=0.8)
mp_draw = mp.solutions.drawing_utils

# --- STATE ---
is_paused = False
is_mouse_mode = False
last_action_time = 0
smooth_angle = 0
prev_mouse_pos = None
selected_char = ""

def get_dist(p1, p2):
    return math.sqrt((p1.x - p2.x)**2 + (p1.y - p2.y)**2)

def is_fist(lms):
    tips = [8, 12, 16, 20]
    return all(get_dist(lms[t], lms[0]) < 0.18 for t in tips)

def is_palm_away(lms, label):
    # Detects if the back of the hand is facing the camera
    if label == "Right": return lms[4].x > lms[17].x
    return lms[4].x < lms[17].x

cap = cv2.VideoCapture(0)

while cap.isOpened():
    success, frame = cap.read()
    if not success: break
    frame = cv2.flip(frame, 1)
    h, w, _ = frame.shape
    results = hands.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))

    r_lms, l_lms = None, None
    r_label, l_label = "", ""
    
    if results.multi_hand_landmarks:
        for i, res in enumerate(results.multi_handedness):
            label = res.classification[0].label
            lm = results.multi_hand_landmarks[i].landmark
            if label == "Right": r_lms, r_label = lm, label
            if label == "Left": l_lms, l_label = lm, label
            mp_draw.draw_landmarks(frame, results.multi_hand_landmarks[i], mp_hands.HAND_CONNECTIONS)

    # 1. SYSTEM GESTURES (Exit & Pause)
    if r_lms and l_lms:
        if is_fist(r_lms) and is_fist(l_lms): break 
        if is_palm_away(r_lms, "Right") and is_palm_away(l_lms, "Left"):
            if time.time() - last_action_time > 1.0:
                is_paused = not is_paused
                last_action_time = time.time()

    if is_paused:
        cv2.putText(frame, "PAUSED", (w//2-100, h//2), 2, 3, (0,0,255), 5)
        cv2.imshow("AirControl Elite", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'): break
        continue

    # 2. MODE TOGGLE (Left Fist)
    if l_lms and is_fist(l_lms) and time.time() - last_action_time > 1.2:
        is_mouse_mode = not is_mouse_mode
        last_action_time = time.time()
        prev_mouse_pos = None

    # 3. CORE LOGIC
    if not is_mouse_mode:
        # --- KEYBOARD MODE (90 DEG DIAL) ---
        if r_lms:
            # RETURN KEY: Right Palm Away
            if is_palm_away(r_lms, "Right") and time.time() - last_action_time > 0.8:
                pyautogui.press('enter'); last_action_time = time.time()

            current_set = SYMBOLS if is_fist(r_lms) else LETTERS
            
            # Fixed Angle Calculation (Inverted for natural spin)
            raw_rad = math.atan2(r_lms[0].y - r_lms[9].y, r_lms[0].x - r_lms[9].x)
            deg = math.degrees(raw_rad) - 90
            deg = max(-90, min(0, deg)) 
            
            # Map deg (-90 to 0) to index (0 to max)
            smooth_angle = (DIAL_SMOOTHING * deg) + ((1 - DIAL_SMOOTHING) * smooth_angle)
            idx = int((abs(smooth_angle) / 90) * (len(current_set) - 1))
            selected_char = current_set[idx]

            # UI DRAWING
            # Background Arc
            cv2.ellipse(frame, (w-50, h-50), (350, 350), 0, 180, 270, (40, 40, 40), 40)
            for i, char in enumerate(current_set):
                # Spread letters along the 180 to 270 degree arc
                a = 180 + (i / (len(current_set)-1) * 90)
                tx = int((w-50) + 380 * math.cos(math.radians(a)))
                ty = int((h-50) + 380 * math.sin(math.radians(a)))
                
                if char == selected_char:
                    cv2.circle(frame, (tx+10, ty-10), 25, (0, 255, 0), -1) # Highlight circle
                    cv2.putText(frame, char, (tx, ty), 1, 2, (255, 255, 255), 3) # Bigger text
                else:
                    cv2.putText(frame, char, (tx, ty), 1, 0.6, (200, 200, 200), 1)

        # Left Hand Triggers
        if l_lms and time.time() - last_action_time > 0.35:
            if get_dist(l_lms[4], l_lms[8]) < PINCH_T: # Index+Thumb: Type
                pyautogui.write(selected_char); last_action_time = time.time()
            elif get_dist(l_lms[4], l_lms[12]) < PINCH_T: # Middle+Thumb: Space
                pyautogui.press('space'); last_action_time = time.time()
            elif get_dist(l_lms[4], l_lms[20]) < PINCH_T: # Pinky+Thumb: Backspace
                pyautogui.press('backspace'); last_action_time = time.time()

    else:
        # --- SCISSORS MOUSE MODE ---
        if r_lms:
            # Movement: Join Index and Middle (Distance threshold, no need to overlap)
            is_moving = get_dist(r_lms[8], r_lms[12]) < 0.05 
            curr_pos = (r_lms[8].x, r_lms[8].y)


            if is_moving:
                if prev_mouse_pos:
                    dx = (curr_pos[0] - prev_mouse_pos[0]) * MOUSE_SENS
                    dy = (curr_pos[1] - prev_mouse_pos[1]) * MOUSE_SENS
                    pyautogui.moveRel(dx, dy)
                prev_mouse_pos = curr_pos
                cv2.putText(frame, "MOVING", (w-150, 50), 1, 1.5, (0,255,0), 2)
            else:
                prev_mouse_pos = None # "Clutch" engaged, mouse parked
                cv2.putText(frame, "PARKED", (w-150, 50), 1, 1.5, (0,0,255), 2)

                # Gestures (While parked)
                if time.time() - last_action_time > 0.4:
                    if get_dist(r_lms[4], r_lms[8]) < PINCH_T: # Left Click
                        pyautogui.click(); last_action_time = time.time()
                    elif get_dist(r_lms[4], r_lms[12]) < PINCH_T: # Right Click
                        pyautogui.rightClick(); last_action_time = time.time()
            
            # Scroll: All fingers except thumb extended upward
            tips = [r_lms[8], r_lms[12], r_lms[16], r_lms[20]]
            if all(t.y < r_lms[6].y for t in tips) and not is_moving:
                if prev_mouse_pos:
                    scroll_dy = (prev_mouse_pos[1] - curr_pos[1]) * 30
                    pyautogui.scroll(int(scroll_dy))
                prev_mouse_pos = curr_pos

    cv2.putText(frame, f"MODE: {'MOUSE' if is_mouse_mode else 'KEYBOARD'}", (20, 50), 1, 1.5, (255, 100, 0), 2)
    cv2.imshow("AirControl Elite", frame)
    if cv2.waitKey(1) & 0xFF == ord('q'): break

cap.release()
cv2.destroyAllWindows()