import streamlit as st
import pandas as pd
import random
import datetime
import firebase_admin
from firebase_admin import auth, credentials, firestore, exceptions
import json

# Firebase setup (Replace with actual Firebase credentials JSON file)
if not firebase_admin._apps:
    cred = credentials.Certificate(json.loads(st.secrets["firebase"].to_json()))
    firebase_admin.initialize_app(cred)

# Initialize Firestore
db = firestore.client()

# Simulated database (Replace with actual database in production)
RIDDLES = [
    {"question": "ما هو الشيء الذي يمشي بلا قدمين؟", "options": ["السيارة", "الظل", "الريح", "النهر"], "answer": "الظل"},
    {"question": "ما هو الشيء الذي يكتب ولا يقرأ؟", "options": ["الكتاب", "الحاسوب", "القلم", "الرسالة"], "answer": "القلم"},
    {"question": "ما هو الشيء الذي كلما أخذت منه كبر؟", "options": ["الثقب", "الحفرة", "البئر", "الهواء"], "answer": "الحفرة"},
]

# User Authentication
st.title("🔐 تسجيل الدخول أو إنشاء حساب جديد")
email = st.text_input("📧 أدخل البريد الإلكتروني:")
password = st.text_input("🔑 أدخل كلمة المرور:", type="password")

if st.button("تسجيل الدخول"):
    try:
        user = auth.get_user_by_email(email)
        st.session_state.user = user.uid
        st.success("✅ تم تسجيل الدخول بنجاح!")
    except exceptions.NotFoundError:
        st.error("❌ البريد الإلكتروني غير مسجل. الرجاء إنشاء حساب جديد.")

if st.button("إنشاء حساب جديد"):
    try:
        user = auth.create_user(email=email, password=password)
        st.session_state.user = user.uid
        db.collection("users").document(user.uid).set({"points": 0, "answered_today": False})
        st.success("🎉 تم إنشاء الحساب بنجاح! يمكنك الآن تسجيل الدخول.")
    except exceptions.FirebaseError as e:
        st.error(f"❌ خطأ في إنشاء الحساب: {e}")

if 'user' in st.session_state:
    st.title("🌙 فوازير رمضان")
    st.subheader("حاول حل الفزورة اليومية واربح النقاط!")

    # Get today's riddle (Rotate based on day)
    today_index = datetime.date.today().day % len(RIDDLES)
    today_riddle = RIDDLES[today_index]

    # Retrieve user points from Firestore
    user_ref = db.collection("users").document(st.session_state.user)
    user_doc = user_ref.get()
    if user_doc.exists:
        user_data = user_doc.to_dict()
        st.session_state.points = user_data.get("points", 0)
        st.session_state.answered_today = user_data.get("answered_today", False)
    else:
        user_ref.set({"points": 0, "answered_today": False})
        st.session_state.points = 0
        st.session_state.answered_today = False

    # If user hasn't answered yet, show the question
    if not st.session_state.answered_today:
        st.write("### فزورة اليوم:")
        st.write(today_riddle["question"])

        # Display MCQ options
        selected_option = st.radio("اختر إجابة:", today_riddle["options"])

        # Answer submission
        if st.button("تحقق من الإجابة"):
            if selected_option == today_riddle["answer"]:
                st.success("🎉 إجابة صحيحة! +10 نقاط")
                st.session_state.points += 10
            else:
                st.error("❌ إجابة خاطئة، حاول مرة أخرى غدًا!")
            
            # Mark as answered and update Firestore
            st.session_state.answered_today = True
            user_ref.update({"points": st.session_state.points, "answered_today": True})
            st.rerun()  # 🔄 Refresh the app to remove the question
    else:
        st.warning("✅ لقد أجبت على فزورة اليوم بالفعل، عد غدًا لفزورة جديدة!")

    # Leaderboard
    st.write("### نقاطك الحالية: ", st.session_state.points)
