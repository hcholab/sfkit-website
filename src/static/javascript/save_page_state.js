$(document).ready(function () {
    var configureStudyModalOpen = Cookies.get('configureStudyModalOpen');
    if (configureStudyModalOpen == null || configureStudyModalOpen == "true") {
        $('#configure_study_modal').modal('show');
    }
    $('#configure_study_modal').on('hidden.bs.modal', function () {
        Cookies.set('configureStudyModalOpen', false);
    });
    $("#configure_study_modal").bind('shown.bs.modal', function () {
        Cookies.set('configureStudyModalOpen', true);
    });


    var lastConfigurationStep = Cookies.get('activeAccordionGroup');
    if (lastConfigurationStep != null) {
        $("#accordion .collapse").removeClass('show');
        $("#accordion .accordion-button").addClass('collapsed');
        $("#" + lastConfigurationStep).collapse("show");
    }
    $("#accordion").bind('shown.bs.collapse', function () {
        var active = $("#accordion .show").attr('id');
        Cookies.set('activeAccordionGroup', active);
    });
});