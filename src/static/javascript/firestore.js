import {initializeApp} from "https://www.gstatic.com/firebasejs/9.6.6/firebase-app.js";
import {getFirestore, doc, onSnapshot} from "https://www.gstatic.com/firebasejs/9.6.6/firebase-firestore.js";
import {getAuth, signInWithCustomToken} from "https://www.gstatic.com/firebasejs/9.6.6/firebase-auth.js";

export function getFirestoreDatabase(custom_token, firebase_api_key) {
  const app = initializeApp({apiKey: firebase_api_key, projectId: "broad-cho-priv1"});
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

      if (doc.data()["study_type"] === "MPCGWAS" || doc.data()["study_type"] === "SFGWAS") {
        document.getElementById("manhattan-div").style.display = "block";

        const imageElement = document.getElementById("my-image");
        const labelElement = document.getElementById("image-label");

        const image = new Image();
        image.src = imageElement.src;

        image.addEventListener("error", event => {
          labelElement.style.display = "none";
        });

        image.addEventListener("load", event => {
          labelElement.style.display = "block";
        });
      }
    }
  });
}

export function getChatUpdates(db, study_title, user_id, display_names) {
  onSnapshot(doc(db, "studies", study_title), doc => {
    const chat_array = doc.data()["messages"];

    if (chat_array.length > 0) {
      const chat = document.getElementById("past_messages");
      chat.innerHTML = "";

      for (const message of chat_array) {
        const messageElement = document.createElement("div");
        messageElement.classList.add("message", "d-flex");
        if (message["sender"] === user_id) {
          messageElement.classList.add("flex-row-reverse");
        } else {
          messageElement.classList.add("flex-row");
        }

        const alertElement = document.createElement("div");
        alertElement.classList.add("alert");
        if (String(message["sender"]) === String(user_id)) {
          alertElement.classList.add("alert-primary");
        } else {
          alertElement.classList.add("alert-secondary");
        }

        const headerElement = document.createElement("div");
        headerElement.classList.add("message-header", "text-start", "mb-2");

        headerElement.innerHTML = `
          <b>
          <span class="message-sender">${display_names[message["sender"]] || message["sender"]}</span>
          </b>
          <span class="message-time text-muted">${message["time"]}</span>
        `;
        alertElement.appendChild(headerElement);

        const bodyElement = document.createElement("div");
        bodyElement.classList.add("message-body", "text-start");
        bodyElement.innerHTML = message["body"];
        alertElement.appendChild(bodyElement);

        messageElement.appendChild(alertElement);
        chat.appendChild(messageElement);
      }
    }
  });
}
