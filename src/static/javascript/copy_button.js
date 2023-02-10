$(document).ready(function () {
  // Get the button
  let btn_tooltip = $("#copy-button");
  let tooltip_text = "Copy to Clipboard";

  // Update Tooltip text on mouse enter
  btn_tooltip.mouseenter(function () {
    btn_tooltip.text(tooltip_text);
  });

  // Update Tooltip text to default on mouse leave
  btn_tooltip.mouseleave(function () {
    btn_tooltip.text("Copy");
  });

  // Update Tooltip text and Copy Text on click
  btn_tooltip.click(function () {
    let copyText = $("#gcloud-command").text().replace(/^\s+/gm, ""); // Remove leading whitespace
    navigator.clipboard.writeText(copyText).then(function () {
      btn_tooltip.text("Copied!");
    }, function () {
      console.log("Failure to copy. Check permissions for clipboard");
    });
  });
});
