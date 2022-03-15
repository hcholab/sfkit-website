$(document).ready(function () {
    // Get the Tooltip
    new bootstrap.Tooltip($('#copy-button'));
    let btn_tooltip = $('#copy-button');

    // Change Tooltip Text on mouse enter
    btn_tooltip.mouseenter(function () {
        btn_tooltip
        .attr('title', 'Copy to Clipboard')
        .tooltip('dispose');
        btn_tooltip.tooltip('show');
    });

    // remove tooltip when user moves mouse away
    btn_tooltip.mouseleave(function () {
        btn_tooltip
        .tooltip('dispose')
        .tooltip('hide');
    });

    // Update Tooltip and Copy Text on click
    btn_tooltip.click(function () {
        let copyText = $('#gcloud-command')
        .text()
        .replace(/^\s+/gm, ''); // Remove leading whitespace
        navigator
        .clipboard
        .writeText(copyText)
        .then(function () {
            btn_tooltip // Update tooltip text
            .attr('title', 'Copied!')
            .tooltip('dispose');
            btn_tooltip.tooltip('show');
        }, function () {
            console.log('Failure to copy. Check permissions for clipboard')
        });
    });
});