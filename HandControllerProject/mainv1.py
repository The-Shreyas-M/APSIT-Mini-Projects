import cv2
import mediapipe as mp
import math
import numpy as np
import pyautogui
import time

# --- SETTINGS ---
pyautogui.PAUSE = 0
pyautogui.FAILSAFE = True
CHARS = " ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890.,!?"
MOUSE_SENSITIVITY = 1800  # Adjust for speed
SCROLL_SENSITIVITY = 20
SMOOTH_ALPHA = 0.2  # For the dial (0-1, lower is smoother)

# MediaPipe Setup
mp_hands = mp.solutions.hands
hands = mp_hands.Hands(max_num_hands=2, min_detection_confidence=0.8, min_tracking_confidence=0.8)
mp_draw = mp.solutions.drawing_utils

# --- STATE VARIABLES ---
is_paused = False
is_mouse_mode = False
last_action_time = 0
smooth_angle = 0
prev_hand_pos = None  # For relative mouse
selected_char = ""

cap = cv2.VideoCapture(0)

def get_dist(p1, p2):
    return math.sqrt((p1.x - p2.x)**2 + (p1.y - p2.y)**2)

def is_fist(lms):
    tips = [8, 12, 16, 20]
    return all(get_dist(lms[t], lms[0]) < 0.15 for t in tips)

def is_palm_away(lms, label):
    # Logic: If Thumb (4) is on the opposite side of Pinky (17) than usual
    if label == "Right":
        return lms[4].x > lms[17].x
    else:
        return lms[4].x < lms[17].x

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

    # --- 1. GLOBAL GESTURES (Exit & Pause) ---
    if r_lms and l_lms:
        # EXIT: Both Fists
        if is_fist(r_lms) and is_fist(l_lms):
            print("System Shutdown..."); break
        
        # PAUSE/RESUME: Both palms flip
        r_away = is_palm_away(r_lms, "Right")
        l_away = is_palm_away(l_lms, "Left")
        if r_away and l_away and not is_paused:
            is_paused = True; print("System Paused")
        elif not r_away and not l_away and is_paused:
            is_paused = False; print("System Resumed")

    if is_paused:
        cv2.putText(frame, "PAUSED", (w//2-100, h//2), 2, 3, (0,0,255), 5)
        cv2.imshow("AirControl Pro", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'): break
        continue

    # --- 2. MODE TOGGLE (Left Hand Fist) ---
    if l_lms and is_fist(l_lms) and time.time() - last_action_time > 1.2:
        is_mouse_mode = not is_mouse_mode
        last_action_time = time.time()
        prev_hand_pos = None # Reset relative tracking

    # --- 3. CORE LOGIC ---
    if not is_mouse_mode:
        # KEYBOARD DIAL
        if r_lms:
            # Smoothing the angle
            raw_rad = math.atan2(r_lms[0].y - r_lms[9].y, r_lms[0].x - r_lms[9].x)
            raw_deg = max(-90, min(90, math.degrees(raw_rad) - 90))
            smooth_angle = (SMOOTH_ALPHA * raw_deg) + ((1 - SMOOTH_ALPHA) * smooth_angle)
            
            idx = int(((smooth_angle + 90) / 180) * (len(CHARS) - 1))
            selected_char = CHARS[idx]

            # Draw Dial UI
            center = (w // 2, h - 50)
            cv2.ellipse(frame, center, (300, 300), 0, 180, 360, (50, 50, 50), 20)
            
            for i, char in enumerate(CHARS):
                angle_pos = ((i / (len(CHARS)-1)) * 180) - 180
                rad = math.radians(angle_pos)
                tx = int(center[0] + 330 * math.cos(rad))
                ty = int(center[1] + 330 * math.sin(rad))
                
                font_scale, color = 0.5, (200, 200, 200)
                if char == selected_char:
                    font_scale, color = 1.2, (0, 255, 0)
                cv2.putText(frame, char, (tx-10, ty), cv2.FONT_HERSHEY_SIMPLEX, font_scale, color, 2)

        # Typing Triggers (Left Hand)
        if l_lms and not is_fist(l_lms) and time.time() - last_action_time > 0.4:
            if get_dist(l_lms[4], l_lms[8]) < 0.05: # Type
                pyautogui.write(selected_char); last_action_time = time.time()
            elif get_dist(l_lms[4], l_lms[20]) < 0.05: # Backspace
                pyautogui.press('backspace'); last_action_time = time.time()

    else:
        # --- RELATIVE MOUSE MODE ---
        if r_lms:
            # Check if Index and Middle are Up (The "Clutch")
            is_moving = r_lms[8].y < r_lms[6].y and r_lms[12].y < r_lms[10].y
            curr_pos = (r_lms[8].x, r_lms[8].y)

            if is_moving:
                if prev_hand_pos:
                    dx = (curr_pos[0] - prev_hand_pos[0]) * MOUSE_SENSITIVITY
                    dy = (curr_pos[1] - prev_hand_pos[1]) * MOUSE_SENSITIVITY
                    pyautogui.moveRel(dx, dy, _pause=False)
                prev_hand_pos = curr_pos
                cv2.putText(frame, "MOVING", (w-150, 50), 1, 1.5, (0,255,0), 2)
            else:
                prev_hand_pos = None # Disconnect the clutch
                cv2.putText(frame, "PARKED", (w-150, 50), 1, 1.5, (0,0,255), 2)

                # Gestures (Only when not moving)
                if time.time() - last_action_time > 0.4:
                    if get_dist(r_lms[4], r_lms[8]) < 0.05: # Left Click
                        pyautogui.click(); last_action_time = time.time()
                    elif get_dist(r_lms[4], r_lms[12]) < 0.05: # Right Click
                        pyautogui.rightClick(); last_action_time = time.time()
            
            # SCROLL: 4 Fingers up (Index, Middle, Ring, Pinky)
            if all(r_lms[t].y < r_lms[t-2].y for t in [8, 12, 16, 20]) and not is_moving:
                # Use hand vertical velocity for scroll
                if prev_hand_pos:
                    dy = (prev_hand_pos[1] - curr_pos[1]) * SCROLL_SENSITIVITY
                    pyautogui.scroll(int(dy))
                prev_hand_pos = curr_pos

    # UI Overlay
    cv2.putText(frame, f"MODE: {'MOUSE' if is_mouse_mode else 'KEYBOARD'}", (20, 50), 1, 2, (255, 255, 0), 2)
    cv2.imshow("AirControl Pro", frame)
    if cv2.waitKey(1) & 0xFF == ord('q'): break

cap.release()
cv2.destroyAllWindows()