import streamlit as st
import pandas as pd
import datetime
import firebase_admin
from firebase_admin import auth, credentials, firestore
import json

# Initialize Firebase
if not firebase_admin._apps:
    cred = credentials.Certificate(json.loads(st.secrets["firebase"].to_json()))
    firebase_admin.initialize_app(cred)

db = firestore.client()

# Sample Riddles
RIDDLES = [
    {"question": "ما هو الشيء الذي يمشي بلا قدمين؟", "options": ["السيارة", "الظل", "الريح", "النهر"], "answer": "الظل"},
    {"question": "ما هو الشيء الذي يكتب ولا يقرأ؟", "options": ["الكتاب", "الحاسوب", "القلم", "الرسالة"], "answer": "القلم"},
    {"question": "ما هو الشيء الذي كلما أخذت منه كبر؟", "options": ["الثقب", "الحفرة", "البئر", "الهواء"], "answer": "الحفرة"},
]

# --- Authentication ---
st.title("فوازير رمضان")

email = st.text_input("📧 بريدك الإلكتروني:")
password = st.text_input("🔑 كلمة المرور:", type="password")

if st.button("تسجيل الدخول"):
    try:
        user = auth.get_user_by_email(email)
        st.session_state.uid = user.uid
        st.session_state.email = user.email
        st.success("تم تسجيل الدخول بنجاح!")
    except:
        st.error("المستخدم غير موجود!")

if st.button("إنشاء حساب جديد"):
    try:
        user = auth.create_user(email=email, password=password)
        st.session_state.uid = user.uid
        st.session_state.email = email
        # Initialize Firestore document
        db.collection("users").document(user.uid).set({
            "email": email,
            "points": 0
        })
        st.success("تم إنشاء الحساب بنجاح!")
    except Exception as e:
        st.error(f"خطأ: {e}")

# --- Ramadan Quiz ---
if 'uid' in st.session_state:
    # Load the user from Firestore
    user_ref = db.collection("users").document(st.session_state.uid)
    doc = user_ref.get()

    if doc.exists:
        user_data = doc.to_dict()
        current_points = user_data.get("points", 0)
    else:
        current_points = 0
        user_ref.set({"email": st.session_state.email, "points": 0})

    # Today's riddle
    idx = datetime.date.today().day % len(RIDDLES)
    riddle = RIDDLES[idx]

    # Check if user already answered today
    today_str = str(datetime.date.today())
    answered_date = user_data.get("answered_date", "")  # store date user answered
    if answered_date == today_str:
        st.info("لقد أجبت بالفعل اليوم! عد غداً.")
    else:
        # Show riddle
        st.subheader("فزورة اليوم:")
        st.write(riddle["question"])
        chosen = st.radio("اختر الإجابة:", riddle["options"])

        if st.button("تحقق من الإجابة"):
            is_correct = (chosen == riddle["answer"])
            if is_correct:
                st.success("إجابة صحيحة!")

                # Count how many have answered correctly today
                # We track those who have "answered_date" == today AND some "answered_correctly_today" field
                correct_today_query = db.collection("users")\
                    .where("answered_date", "==", today_str)\
                    .where("answered_correctly_today", "==", True)

                already_correct = len(correct_today_query.get())

                # Decide how many points to give
                if already_correct == 0:
                    add_points = 15
                elif already_correct == 1:
                    add_points = 10
                elif already_correct == 2:
                    add_points = 5
                else:
                    add_points = 0

                if add_points > 0:
                    st.success(f"حصلت على {add_points} نقاط إضافية!")
                else:
                    st.info("لم تحصل على نقاط لأنك لست ضمن الثلاثة الأوائل.")

                new_points = current_points + add_points
                user_ref.update({
                    "points": new_points,
                    "answered_date": today_str,
                    "answered_correctly_today": True
                })
            else:
                st.error("إجابة خاطئة! حاول مرة أخرى غداً.")

                user_ref.update({
                    "answered_date": today_str,
                    "answered_correctly_today": False
                })

    # --- Leaderboard ---
    st.header("لوحة الصدارة")
    # Only show those who answered at some time (any time) with points desc
    lb_query = db.collection("users").order_by("points", direction=firestore.Query.DESCENDING).limit(10)
    lb_docs = lb_query.get()

    data = []
    rank = 1
    user_position = None
    for d in lb_docs:
        info = d.to_dict()
        data.append([rank, info.get("email", "مجهول"), info.get("points", 0)])
        if d.id == st.session_state.uid:
            user_position = rank
        rank += 1

    df = pd.DataFrame(data, columns=["المركز","البريد الإلكتروني","النقاط"])
    st.table(df)

    if user_position:
        st.write(f"ترتيبك الحالي: #{user_position}")
    else:
        st.write("أنت خارج أفضل 10.")

