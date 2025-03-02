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
            "correct_answer": False
        })
        st.session_state.points = 0
        st.session_state.answered_today = False
        st.session_state.correct_answer = False

    # 🏆 **Leaderboard (Only Correct Answers)**
    users_ref = db.collection("users")\
        .where("correct_answer", "==", True)\
        .order_by("points", direction=firestore.Query.DESCENDING)\
        .limit(3)

    top_users = []
    for idx, doc in enumerate(users_ref.stream(), start=1):
        data = doc.to_dict()
        email_display = data.get("email", f"غير معروف_{idx}")
        top_users.append({"rank": idx, "uid": doc.id, "email": email_display, "points": data["points"]})

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
                # Determine if the user is in the top 3
                user_rank = get_user_rank()

                if user_rank == 1:
                    earned_points = 15
                elif user_rank == 2:
                    earned_points = 10
                elif user_rank == 3:
                    earned_points = 5
                else:
                    earned_points = 0

                st.success(f"🎉 إجابة صحيحة! +{earned_points} نقاط")
                st.session_state.points += earned_points
            else:
                st.error("❌ إجابة خاطئة! لن تتمكن من المحاولة مرة أخرى اليوم.")

            # Mark as answered and update Firestore
            st.session_state.answered_today = True
            st.session_state.correct_answer = is_correct
            user_ref.update({
                "points": st.session_state.points,
                "last_answer_date": today_date,
                "correct_answer": is_correct
            })
            st.rerun()

    else:
        if st.session_state.correct_answer:
            st.success("✅ لقد أجبت على الفزورة بشكل صحيح اليوم! عد غدًا لفزورة جديدة.")
        else:
            st.error("❌ لقد أجبت بشكل خاطئ اليوم، حاول مرة أخرى غدًا!")

    # Show user's points
    st.write("### نقاطك الحالية: ", st.session_state.points)

    # 🏆 **Leaderboard (Only Correct Answers)**
    st.title("🏆 لوحة الصدارة")

    leaderboard = []
    user_rank = get_user_rank()
    for user in top_users:
        leaderboard.append({"المركز": user["rank"], "البريد الإلكتروني": user["email"], "النقاط": user["points"]})

    # Display leaderboard
    df_leaderboard = pd.DataFrame(leaderboard)
    df_leaderboard.index += 1
    st.table(df_leaderboard)

    # Show user's position (Only if they answered correctly)
    if st.session_state.correct_answer and user_rank:
        st.write(f"📍 **ترتيبك بين الذين أجابوا بشكل صحيح:** **#{user_rank}** 🎯")
    elif not st.session_state.correct_answer:
        st.write("😞 لم تجب على السؤال بشكل صحيح اليوم، حاول مرة أخرى غدًا!")
