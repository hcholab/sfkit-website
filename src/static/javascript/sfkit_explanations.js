$("#a").mouseenter(function () {
  document.getElementById("Authentication").style.display = "block";

  document.getElementById("Networking").style.display = "none";
  document.getElementById("KeyExchange").style.display = "none";
  document.getElementById("DataValidation").style.display = "none";
  document.getElementById("RunProtocol").style.display = "none";
});
$("#b").mouseenter(function () {
  document.getElementById("Networking").style.display = "block";

  document.getElementById("Authentication").style.display = "none";
  document.getElementById("KeyExchange").style.display = "none";
  document.getElementById("DataValidation").style.display = "none";
  document.getElementById("RunProtocol").style.display = "none";
});
$("#c").mouseenter(function () {
  document.getElementById("KeyExchange").style.display = "block";

  document.getElementById("Authentication").style.display = "none";
  document.getElementById("Networking").style.display = "none";
  document.getElementById("DataValidation").style.display = "none";
  document.getElementById("RunProtocol").style.display = "none";
});
$("#d").mouseenter(function () {
  document.getElementById("DataValidation").style.display = "block";

  document.getElementById("Authentication").style.display = "none";
  document.getElementById("Networking").style.display = "none";
  document.getElementById("KeyExchange").style.display = "none";
  document.getElementById("RunProtocol").style.display = "none";
});
$("#e").mouseenter(function () {
  document.getElementById("RunProtocol").style.display = "block";

  document.getElementById("Authentication").style.display = "none";
  document.getElementById("Networking").style.display = "none";
  document.getElementById("KeyExchange").style.display = "none";
  document.getElementById("DataValidation").style.display = "none";
});
