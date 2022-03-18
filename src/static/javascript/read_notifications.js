import {initializeApp} from "https://www.gstatic.com/firebasejs/9.6.6/firebase-app.js";
import {getFirestore, doc, onSnapshot} from "https://www.gstatic.com/firebasejs/9.6.6/firebase-firestore.js";
import {getAuth, signInWithCustomToken} from "https://www.gstatic.com/firebasejs/9.6.6/firebase-auth.js"
$(document).ready(function () {
    const id = $('#id-data').data()['value'];
    const firebaseConfig = {
        apiKey: "AIzaSyAJ5Ql7iZ4QMi640Xryx0YbBzwhGdGxKdE",
        authDomain: "broad-cho-priv1.firebaseapp.com",
        projectId: "broad-cho-priv1",
        storageBucket: "broad-cho-priv1.appspot.com",
        messagingSenderId: "419003787216",
        appId: "1:419003787216:web:1128a872a2eb31c00cfbd5",
        measurementId: "G-FV14RX2JXN",
        databaseURL: "",
        serviceAccount: "serviceAccountKey.json"
    };
    const app = initializeApp(firebaseConfig);
    const db = getFirestore(app);
    const auth = getAuth(app);
    signInWithCustomToken(auth, custom_token);
  
    onSnapshot(doc(db, "users", id), (doc) => {
        const notifications = doc.data()["notifications"];

        if (notifications.length > 0) {
            const num_notifications = document.getElementById("num_notifications");
            num_notifications.classList.remove("bg-secondary")
            num_notifications.classList.add("bg-danger")
            num_notifications.innerHTML = notifications.length;

            const no_notifications = document.getElementById("no_notifications");
            if (no_notifications) {
                no_notifications.remove();
            }

            document.getElementById("notification_list").innerHTML = '';
            
            const p = document.createElement("p");
            p.classList.add("text-center", "small", "mb-2", "mt-2");
            p.innerHTML = "Notifications";
            document.getElementById("notification_list").appendChild(p);

            for (const notification of notifications) {
                addNotificationToList(notification);
            }
        } else {
            const num_notifications = document.getElementById("num_notifications");
            num_notifications.classList.remove("bg-danger")
            num_notifications.classList.add("bg-secondary")
            num_notifications.innerHTML = 0;
            const no_notifications = document.getElementById("no_notifications");
            if (!no_notifications) {
                const li = document.createElement("li");
                li.id = "no_notifications";
                li.classList.add("dropdown-item-text", "text-center", "text-muted");
                li.innerHTML = "No notifications";
                document.getElementById("notification_list").appendChild(li);
            }
        }
    })
});

function addNotificationToList(notification) {
    const li = document.createElement("li");
    const span = document.createElement("span");
    span.classList.add("dropdown-item-text", "alert", "alert-info", "alert-dismissible", "mb-0", "mt-0", "text-muted", "small");
    span.innerHTML = notification;
    const button = document.createElement("button");
    button.classList.add("btn-sm", "btn-close");
    button.setAttribute("type", "button");
    button.setAttribute("data-bs-dismiss", "alert");
    button.setAttribute("onclick", "removeNotification(this.parentElement.innerHTML.split('<')[0])");
    
    span.appendChild(button);
    li.appendChild(span);
    document.getElementById("notification_list").appendChild(li);
}