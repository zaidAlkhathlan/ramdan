import streamlit as st
import pandas as pd
import datetime
import firebase_admin
from firebase_admin import auth, credentials, firestore, exceptions

# Firebase setup
if not firebase_admin._apps:
    cred = credentials.Certificate(dict(st.secrets["firebase"]))
    firebase_admin.initialize_app(cred)

# Initialize Firestore
db = firestore.client()

# Simulated riddles
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
        st.session_state.email = email  # Store email for leaderboard
        st.success("✅ تم تسجيل الدخول بنجاح!")
    except exceptions.NotFoundError:
        st.error("❌ البريد الإلكتروني غير مسجل. الرجاء إنشاء حساب جديد.")

if st.button("إنشاء حساب جديد"):
    try:
        user = auth.create_user(email=email, password=password)
        st.session_state.user = user.uid
        st.session_state.email = email
        db.collection("users").document(user.uid).set({"email": email, "points": 0, "answered_today": False})
        st.success("🎉 تم إنشاء الحساب بنجاح! يمكنك الآن تسجيل الدخول.")
    except exceptions.FirebaseError as e:
        st.error(f"❌ خطأ في إنشاء الحساب: {e}")

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
        st.session_state.answered_today = user_data.get("answered_today", False)
    else:
        user_ref.set({"email": st.session_state.email, "points": 0, "answered_today": False})
        st.session_state.points = 0
        st.session_state.answered_today = False

    st.write("### فزورة اليوم:")
    st.write(today_riddle["question"])

    # MCQ Options
    selected_option = st.radio("اختر إجابة:", today_riddle["options"])

    # Check if user can answer
    if not st.session_state.answered_today:
        if st.button("تحقق من الإجابة"):
            if selected_option == today_riddle["answer"]:
                st.success("🎉 إجابة صحيحة!")

                # Fetch the first 3 correct answers from Firestore
                correct_users = db.collection("users").where("answered_today", "==", True).order_by("points", direction=firestore.Query.DESCENDING).limit(3).get()
                correct_count = len(correct_users)

                if correct_count == 0:
                    points_awarded = 15
                elif correct_count == 1:
                    points_awarded = 10
                elif correct_count == 2:
                    points_awarded = 5
                else:
                    points_awarded = 0  # No points for users beyond the top 3

                if points_awarded > 0:
                    new_points = st.session_state.points + points_awarded
                    user_ref.update({"points": new_points, "answered_today": True})
                    st.session_state.points = new_points
                    st.success(f"🎉 حصلت على {points_awarded} نقاط!")

            else:
                st.error("❌ إجابة خاطئة، لا يمكنك المحاولة مجددًا!")
                user_ref.update({"answered_today": True})
                st.session_state.answered_today = True

    else:
        st.warning("لقد أجبت على فزورة اليوم بالفعل، عد غدًا لفزورة جديدة!")

    # 🏆 Leaderboard
    st.subheader("🏆 لوحة الصدارة")
    leaderboard_query = db.collection("users").order_by("points", direction=firestore.Query.DESCENDING).limit(10)
    leaderboard_users = leaderboard_query.get()

    leaderboard_data = []
    for i, user in enumerate(leaderboard_users):
        user_info = user.to_dict()
        leaderboard_data.append([i + 1, user_info.get("email", "مجهول"), user_info.get("points", 0)])

    df = pd.DataFrame(leaderboard_data, columns=["المركز", "البريد الإلكتروني", "النقاط"])
    st.table(df)

    # 🔎 Show user rank
    user_rank = next((i + 1 for i, user in enumerate(leaderboard_users) if user.id == st.session_state.user), None)
    if user_rank:
        st.markdown(f"📍 **ترتيبك في لوحة الصدارة:** 🎯 #{user_rank}")
