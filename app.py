import streamlit as st
import pandas as pd
import datetime
import firebase_admin
from firebase_admin import auth, credentials, firestore, exceptions
import json

# Firebase setup
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
        db.collection("users").document(user.uid).set({"email": email, "points": 0, "last_answer_date": "", "correct_answer": None})
        st.success("🎉 تم إنشاء الحساب بنجاح! يمكنك الآن تسجيل الدخول.")
    except exceptions.FirebaseError as e:
        st.error(f"❌ خطأ في إنشاء الحساب: {e}")

if 'user' in st.session_state:
    st.title("🌙 فوازير رمضان")
    st.subheader("حاول حل الفزورة اليومية واربح النقاط!")

    # Get today's riddle (Rotate based on day)
    today_index = datetime.date.today().day % len(RIDDLES)
    today_riddle = RIDDLES[today_index]

    # Retrieve user data from Firestore
    user_ref = db.collection("users").document(st.session_state.user)
    user_doc = user_ref.get()
    
    if user_doc.exists:
        user_data = user_doc.to_dict()
        st.session_state.points = user_data.get("points", 0)
        last_answer_date = user_data.get("last_answer_date", "")
        st.session_state.correct_answer = user_data.get("correct_answer", None)

        # Check if user has answered today
        today_date = datetime.date.today().isoformat()
        st.session_state.answered_today = (last_answer_date == today_date)
    else:
        user_ref.set({"email": email, "points": 0, "last_answer_date": "", "correct_answer": None})
        st.session_state.points = 0
        st.session_state.answered_today = False
        st.session_state.correct_answer = None

    # If user has not answered today, show the question
    if not st.session_state.answered_today:
        st.write("### فزورة اليوم:")
        st.write(today_riddle["question"])

        # Display MCQ options
        selected_option = st.radio("اختر إجابة:", today_riddle["options"], index=None)

        # Answer submission
        if selected_option and st.button("تحقق من الإجابة"):
            is_correct = selected_option == today_riddle["answer"]
            
            if is_correct:
                st.success("🎉 إجابة صحيحة! +10 نقاط")
                st.session_state.points += 10
            else:
                st.error("❌ إجابة خاطئة، حاول مرة أخرى غدًا!")

            # Mark as answered for today and update Firestore
            st.session_state.answered_today = True
            st.session_state.correct_answer = is_correct
            user_ref.update({"points": st.session_state.points, "last_answer_date": today_date, "correct_answer": is_correct})
            st.rerun()  # 🔄 Refresh to remove question

    else:
        if st.session_state.correct_answer:
            st.success("✅ لقد أجبت على الفزورة بشكل صحيح اليوم! عد غدًا لفزورة جديدة.")
        else:
            st.error("❌ لقد أجبت بشكل خاطئ اليوم، حاول مرة أخرى غدًا!")
    
    # Display user points
    st.write("### نقاطك الحالية: ", st.session_state.points)

    # 🔥 **Leaderboard: Get top users from Firestore**
    st.title("🏆 لوحة الصدارة")

    users_ref = db.collection("users").order_by("points", direction=firestore.Query.DESCENDING).limit(10)
    users = users_ref.stream()

    leaderboard = []
    user_rank = None
    for idx, doc in enumerate(users, start=1):
        data = doc.to_dict()
        leaderboard.append({"المركز": idx, "البريد الإلكتروني": data["email"], "النقاط": data["points"]})
        if doc.id == st.session_state.user:
            user_rank = idx  # Store logged-in user's position

    # Display leaderboard
    df_leaderboard = pd.DataFrame(leaderboard)
    st.table(df_leaderboard)

    # 🔹 **User Rank**
    if user_rank:
        st.write(f"📍 **ترتيبك في لوحة الصدارة:** **#{user_rank}** 🎯")
    else:
        st.write("😞 لم تصل بعد إلى قائمة أفضل 10 لاعبين، حاول تحسين أدائك!")
