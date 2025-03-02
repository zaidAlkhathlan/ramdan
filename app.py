import streamlit as st
import pandas as pd
import datetime
import firebase_admin
from firebase_admin import auth, credentials, firestore, exceptions
import json

# Initialize Firebase
if not firebase_admin._apps:
    cred = credentials.Certificate(json.loads(st.secrets["firebase"].to_json()))
    firebase_admin.initialize_app(cred)

# Firestore
db = firestore.client()

# Sample Riddles
RIDDLES = [
    {"question": "ما هو الشيء الذي يمشي بلا قدمين؟", "options": ["السيارة", "الظل", "الريح", "النهر"], "answer": "الظل"},
    {"question": "ما هو الشيء الذي يكتب ولا يقرأ؟", "options": ["الكتاب", "الحاسوب", "القلم", "الرسالة"], "answer": "القلم"},
    {"question": "ما هو الشيء الذي كلما أخذت منه كبر؟", "options": ["الثقب", "الحفرة", "البئر", "الهواء"], "answer": "الحفرة"},
]

# 🔐 User Authentication
st.title("🔐 تسجيل الدخول أو إنشاء حساب جديد")
email = st.text_input("📧 أدخل البريد الإلكتروني:")
password = st.text_input("🔑 أدخل كلمة المرور:", type="password")

if st.button("تسجيل الدخول"):
    try:
        user = auth.get_user_by_email(email)
        st.session_state.user = user.uid
        st.session_state.email = user.email  # Ensure email is stored

        # Store email in Firestore if missing
        user_ref = db.collection("users").document(user.uid)
        user_ref.set({"email": user.email}, merge=True)

        st.success("✅ تم تسجيل الدخول بنجاح!")
    except exceptions.NotFoundError:
        st.error("❌ البريد الإلكتروني غير مسجل. الرجاء إنشاء حساب جديد.")

if st.button("إنشاء حساب جديد"):
    try:
        user = auth.create_user(email=email, password=password)
        st.session_state.user = user.uid
        st.session_state.email = email  # Store email in session

        # Save user data in Firestore
        db.collection("users").document(user.uid).set({
            "email": email,
            "points": 0,
            "last_answer_date": "",
            "last_points_update": "",  # ✅ Track when points were last awarded
            "correct_answer": False
        })

        st.success("🎉 تم إنشاء الحساب بنجاح! يمكنك الآن تسجيل الدخول.")
    except exceptions.FirebaseError as e:
        st.error(f"❌ خطأ في إنشاء الحساب: {e}")

# 🌙 Ramadan Quiz
if 'user' in st.session_state:
    st.title("🌙 فوازير رمضان")
    st.subheader("حاول حل الفزورة اليومية واربح النقاط!")

    # Get today's riddle
    today_index = datetime.date.today().day % len(RIDDLES)
    today_riddle = RIDDLES[today_index]

    # Retrieve user data
    user_ref = db.collection("users").document(st.session_state.user)
    user_doc = user_ref.get()

    if user_doc.exists:
        user_data = user_doc.to_dict()
        st.session_state.points = user_data.get("points", 0)
        last_answer_date = user_data.get("last_answer_date", "")
        last_points_update = user_data.get("last_points_update", "")
        st.session_state.correct_answer = user_data.get("correct_answer", False)

        # Ensure email is stored
        if "email" in user_data:
            st.session_state.email = user_data["email"]
        else:
            user_ref.update({"email": st.session_state.email}, merge=True)

        # Check if user has already answered today
        today_date = datetime.date.today().isoformat()
        st.session_state.answered_today = (last_answer_date == today_date)
    else:
        user_ref.set({
            "email": st.session_state.email, 
            "points": 0, 
            "last_answer_date": "", 
            "last_points_update": "",
            "correct_answer": False
        })
        st.session_state.points = 0
        st.session_state.answered_today = False
        st.session_state.correct_answer = False

    # Show the riddle if the user hasn't answered today
    if not st.session_state.answered_today:
        st.write("### فزورة اليوم:")
        st.write(today_riddle["question"])

        # Display answer options
        selected_option = st.radio("اختر إجابة:", today_riddle["options"], index=None)

        # Submit Answer
        if selected_option and st.button("تحقق من الإجابة"):
            is_correct = selected_option == today_riddle["answer"]
            
            if is_correct:
                user_ref.update({"correct_answer": True})

            st.session_state.answered_today = True
            st.session_state.correct_answer = is_correct
            user_ref.update({"last_answer_date": today_date})
            st.rerun()

    # 🏆 **Leaderboard (Only Correct Answers)**
    users_ref = db.collection("users")\
        .where("correct_answer", "==", True)\
        .order_by("points", direction=firestore.Query.DESCENDING)\
        .limit(3)

    top_users = []
    for doc in users_ref.stream():
        data = doc.to_dict()
        top_users.append({
            "uid": doc.id,  
            "email": data.get("email", "غير معروف"), 
            "points": data.get("points", 0),
            "last_points_update": data.get("last_points_update", "")
        })
    
    # Award points **only once per day**
    today_date = datetime.date.today().isoformat()
    for idx, user in enumerate(top_users):
        if user["last_points_update"] != today_date:  # ✅ Prevent multiple updates
            if idx == 0:
                points_to_add = 15
            elif idx == 1:
                points_to_add = 10
            elif idx == 2:
                points_to_add = 5
            else:
                points_to_add = 0

            user_ref = db.collection("users").document(user["uid"])
            user_ref.update({
                "points": firestore.Increment(points_to_add),
                "last_points_update": today_date  # ✅ Mark points update date
            })

    # Function to get the rank of the current user (Only if correct)
    def get_user_rank():
        all_users_ref = db.collection("users")\
            .where("correct_answer", "==", True)\
            .order_by("points", direction=firestore.Query.DESCENDING)

        all_users = all_users_ref.stream()
        for idx, doc in enumerate(all_users, start=1):
            if doc.id == st.session_state.user:
                return idx
        return None

    # Show user's points
    st.write("### نقاطك الحالية: ", st.session_state.points)

    # 🏆 **Leaderboard Display**
    st.title("🏆 لوحة الصدارة")

    leaderboard = []
    user_rank = get_user_rank()
    for idx, user in enumerate(top_users, start=1):
        leaderboard.append({
            "المركز": idx, 
            "البريد الإلكتروني": user.get("email", "غير معروف"), 
            "النقاط": user["points"]
        })

    # Display leaderboard
    df_leaderboard = pd.DataFrame(leaderboard)
    df_leaderboard.index += 1
    st.table(df_leaderboard)

    # Show user's position (Only if they answered correctly)
    if st.session_state.correct_answer and user_rank:
        st.write(f"📍 **ترتيبك بين الذين أجابوا بشكل صحيح:** **#{user_rank}** 🎯")
    elif not st.session_state.correct_answer:
        st.write("😞 لم تجب على السؤال بشكل صحيح اليوم، حاول مرة أخرى غدًا!")
