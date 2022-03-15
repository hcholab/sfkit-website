import {initializeApp} from "https://www.gstatic.com/firebasejs/9.6.6/firebase-app.js";
import {getFirestore, doc, onSnapshot} from "https://www.gstatic.com/firebasejs/9.6.6/firebase-firestore.js";
import {getAuth, signInWithCustomToken} from "https://www.gstatic.com/firebasejs/9.6.6/firebase-auth.js"
$(document).ready(function () {
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
    // const custom_token = "{{g.custom_token}}"; // now in the html
    const auth = getAuth(app);
    signInWithCustomToken(auth, custom_token);
    var study_title = $('#study-title-data')
        .data()['value']
        .toLowerCase()
        .replace(/\s/g, '');
    var id = $('#id-data').data()['value'];
    onSnapshot(doc(db, "studies", study_title), (doc) => {
        $("div.status").html(doc.data()["status"][id].reduce((acc, curr) => acc + "<br>" + curr));
    });
});