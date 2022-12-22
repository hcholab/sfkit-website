import {initializeApp} from "https://www.gstatic.com/firebasejs/9.6.6/firebase-app.js";
import {getFirestore, doc, onSnapshot} from "https://www.gstatic.com/firebasejs/9.6.6/firebase-firestore.js";
import {getAuth, signInWithCustomToken} from "https://www.gstatic.com/firebasejs/9.6.6/firebase-auth.js";

export function getFirestoreDatabase(custom_token) {
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
  const auth = getAuth(app);
  signInWithCustomToken(auth, custom_token);

  const db = getFirestore(app);
  return db;
}

export function readNotifications(db, user_id) {
  onSnapshot(doc(db, "users", user_id), doc => {
    const notifications = doc.data()["notifications"] || [];
    const notification_list = document.getElementById("notification_list");
    notification_list.innerHTML = "";

    if (notifications.length > 0) {
      const num_notifications = document.getElementById("num_notifications");
      num_notifications.classList.remove("bg-secondary");
      num_notifications.classList.add("bg-danger");
      num_notifications.innerHTML = notifications.length;

      const no_notifications = document.getElementById("no_notifications");
      if (no_notifications) {
        no_notifications.remove();
      }

      const p = document.createElement("p");
      p.classList.add("text-center", "small", "mb-2", "mt-2");
      p.innerHTML = "Notifications";
      notification_list.appendChild(p);

      for (const notification of notifications) {
        addNotificationToList(notification);
      }
    } else {
      const num_notifications = document.getElementById("num_notifications");
      num_notifications.classList.remove("bg-danger");
      num_notifications.classList.add("bg-secondary");
      num_notifications.innerHTML = 0;

      const no_notifications = document.getElementById("no_notifications");
      if (!no_notifications) {
        const li = document.createElement("li");
        li.id = "no_notifications";
        li.classList.add("dropdown-item-text", "text-center", "text-muted");
        li.innerHTML = "No new notifications";
        notification_list.appendChild(li);
      }
    }
    const all_notifications = document.createElement("li");
    all_notifications.classList.add("dropdown-item-text", "text-center");
    const all_notifications_link = document.createElement("a");
    all_notifications_link.setAttribute("href", "/profile/" + user_id);
    all_notifications_link.innerHTML = "Profile";
    all_notifications_link.classList.add("text-decoration-none");
    all_notifications.appendChild(all_notifications_link);
    notification_list.appendChild(document.createElement("hr"));
    notification_list.appendChild(all_notifications);
  });
}

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

export function getStatusUpdates(db, study_title, user_id) {
  onSnapshot(doc(db, "studies", study_title), doc => {
    $("div.status").html(doc.data()["status"][user_id]);
    if (doc.data()["status"][user_id].includes("Finished protocol")) {
      document.getElementById("download-div").style.display = "block";
      document.getElementById("check-for-update").style.display = "none";

      // make div that has image from static/images/{study_title}_manhattan.png
      const manhattan = document.createElement("img");
      manhattan.setAttribute("src", "/static/images/" + study_title + "_manhattan.png");
      manhattan.setAttribute("alt", "Please click 'Download results' and reload page to show Manhattan plot");
      manhattan.setAttribute("width", "100%");
      manhattan.setAttribute("height", "100%");
      document.getElementById("manhattan-div").appendChild(manhattan);
    }
  });
}
