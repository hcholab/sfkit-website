$("#a").mouseenter(function () {
  $(this).addClass("border border-secondary");

  document.getElementById("Authentication").style.display = "block";

  document.getElementById("Networking").style.display = "none";
  document.getElementById("KeyExchange").style.display = "none";
  document.getElementById("DataValidation").style.display = "none";
  document.getElementById("RunProtocol").style.display = "none";
});
$("#b").mouseenter(function () {
  $(this).addClass("border border-secondary");

  document.getElementById("Networking").style.display = "block";

  document.getElementById("Authentication").style.display = "none";
  document.getElementById("KeyExchange").style.display = "none";
  document.getElementById("DataValidation").style.display = "none";
  document.getElementById("RunProtocol").style.display = "none";
});
$("#c").mouseenter(function () {
  $(this).addClass("border border-secondary");

  document.getElementById("KeyExchange").style.display = "block";

  document.getElementById("Authentication").style.display = "none";
  document.getElementById("Networking").style.display = "none";
  document.getElementById("DataValidation").style.display = "none";
  document.getElementById("RunProtocol").style.display = "none";
});
$("#d").mouseenter(function () {
  $(this).addClass("border border-secondary");

  document.getElementById("DataValidation").style.display = "block";

  document.getElementById("Authentication").style.display = "none";
  document.getElementById("Networking").style.display = "none";
  document.getElementById("KeyExchange").style.display = "none";
  document.getElementById("RunProtocol").style.display = "none";
});
$("#e").mouseenter(function () {
  $(this).addClass("border border-secondary");

  document.getElementById("RunProtocol").style.display = "block";

  document.getElementById("Authentication").style.display = "none";
  document.getElementById("Networking").style.display = "none";
  document.getElementById("KeyExchange").style.display = "none";
  document.getElementById("DataValidation").style.display = "none";
});

$("#a").mouseleave(function () {
  $(this).removeClass("border border-secondary");
});

$("#b").mouseleave(function () {
  $(this).removeClass("border border-secondary");
});

$("#c").mouseleave(function () {
  $(this).removeClass("border border-secondary");
});

$("#d").mouseleave(function () {
  $(this).removeClass("border border-secondary");
});

$("#e").mouseleave(function () {
  $(this).removeClass("border border-secondary");
});
