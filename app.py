import streamlit as st
import pandas as pd
import datetime
import firebase_admin
from firebase_admin import auth, credentials, firestore, exceptions
import json

# Only show the riddle between 7:00 PM and 7:05 PM local time
def can_show_riddle():
    now = datetime.datetime.now()  # local server time
    start_time = now.replace(hour=00, minute=58, second=0, microsecond=0)  # 7:00 PM
    end_time   = now.replace(hour=19, minute=5, second=0, microsecond=0)  # 7:05 PM
    return start_time <= now <= end_time

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

# ---------------------------------------------------------------------
#                          AUTHENTICATION
# ---------------------------------------------------------------------
st.title("🌙 فوازير رمضان")

email = st.text_input("📧 أدخل البريد الإلكتروني:")
password = st.text_input("🔑 أدخل كلمة المرور:", type="password")

if st.button("تسجيل الدخول"):
    try:
        user = auth.get_user_by_email(email)
        st.session_state.user = user.uid
        st.session_state.email = user.email  # Store email
        # Ensure Firestore doc has an email field
        user_ref = db.collection("users").document(user.uid)
        user_ref.set({"email": user.email}, merge=True)

        st.success("✅ تم تسجيل الدخول بنجاح!")
    except exceptions.NotFoundError:
        st.error("❌ البريد الإلكتروني غير مسجل. الرجاء إنشاء حساب جديد.")

if st.button("إنشاء حساب جديد"):
    try:
        user = auth.create_user(email=email, password=password)
        st.session_state.user = user.uid
        st.session_state.email = email
        # Initialize Firestore doc
        db.collection("users").document(user.uid).set({
            "email": email,
            "points": 0,
            "last_answer_date": "",
            "answered_correctly_today": False
        })
        st.success("🎉 تم إنشاء الحساب بنجاح! يمكنك الآن تسجيل الدخول.")
    except exceptions.FirebaseError as e:
        st.error(f"❌ خطأ في إنشاء الحساب: {e}")

# ---------------------------------------------------------------------
#                          MAIN QUIZ LOGIC
# ---------------------------------------------------------------------
if 'user' in st.session_state:
    st.subheader("حاول حل الفزورة اليومية واربح النقاط!")

    # Load user from Firestore
    user_ref = db.collection("users").document(st.session_state.user)
    doc = user_ref.get()
    if doc.exists:
        user_data = doc.to_dict()
        current_points = user_data.get("points", 0)
        answered_date  = user_data.get("last_answer_date", "")
        answered_correctly_today = user_data.get("answered_correctly_today", False)
    else:
        current_points = 0
        answered_date  = ""
        answered_correctly_today = False
        user_ref.set({
            "email": st.session_state.email,
            "points": 0,
            "last_answer_date": "",
            "answered_correctly_today": False
        })

    # Today's riddle
    riddle_idx = datetime.date.today().day % len(RIDDLES)
    riddle     = RIDDLES[riddle_idx]
    today_str  = str(datetime.date.today())

    # -----------------------------------------------------------------
    #   RIDDLE WINDOW: Only show if now is between 7:00–7:05 PM
    # -----------------------------------------------------------------
    if can_show_riddle():
        st.info("الوقت مفتوح الآن للإجابة: ٧:٠٠ إلى ٧:٠٥ مساءً.")

        # Check if user already answered today
        if answered_date == today_str:
            st.warning("لقد أجبت بالفعل اليوم! عد غدًا.")
        else:
            # Show the riddle
            st.write("### فزورة اليوم:")
            st.write(riddle["question"])
            chosen = st.radio("اختر إجابة:", riddle["options"], index=0)

            if st.button("تحقق من الإجابة"):
                is_correct = (chosen == riddle["answer"])
                if is_correct:
                    st.success("إجابة صحيحة!")
                    # Determine how many have already answered correctly today
                    correct_docs = db.collection("users")\
                        .where("last_answer_date", "==", today_str)\
                        .where("answered_correctly_today", "==", True).get()
                    count_correct_today = len(correct_docs)

                    # Award points only to the first 3 correct answers each day
                    if count_correct_today == 0:
                        add_points = 15
                    elif count_correct_today == 1:
                        add_points = 10
                    elif count_correct_today == 2:
                        add_points = 5
                    else:
                        add_points = 0  # no points beyond the 3rd correct user

                    new_points = current_points + add_points
                    user_ref.update({
                        "points": new_points,
                        "last_answer_date": today_str,
                        "answered_correctly_today": True
                    })

                    st.success(f"حصلت على {add_points} نقاط إضافية!")
                else:
                    st.error("إجابة خاطئة! حاول مرة أخرى غدًا.")
                    user_ref.update({
                        "last_answer_date": today_str,
                        "answered_correctly_today": False
                    })

    else:
        # Outside 7:00–7:05 PM
        st.warning("حاليًا لا يمكنك الإجابة! يرجى العودة من ٧:٠٠ إلى ٧:٠٥ مساءً.")

    # -----------------------------------------------------------------
    #                         LEADERBOARD
    # -----------------------------------------------------------------
    st.title("🏆 لوحة الصدارة")

    # Query all users sorted by points desc, limit 10
    lb_query = db.collection("users").order_by("points", direction=firestore.Query.DESCENDING).limit(10)
    lb_docs  = lb_query.get()

    data = []
    rank = 1
    user_position = None
    for d in lb_docs:
        info = d.to_dict()
        data.append([rank, info.get("email", "مجهول"), info.get("points", 0)])
        if d.id == st.session_state.user:
            user_position = rank
        rank += 1

    df = pd.DataFrame(data, columns=["المركز","البريد الإلكتروني","النقاط"])
    st.table(df)

    if user_position:
        st.write(f"ترتيبك الحالي في لوحة الصدارة: #{user_position}")
    else:
        st.write("أنت خارج أفضل 10.")

