var autoItems = [];

$(document).ready(() => {
    // Pre-fill Trafikverket API key if cached.
  if (localStorage.getItem("tv_api_key")) {
    $("#tvApiKey").val(localStorage.getItem("tv_api_key"));
  }

  if (localStorage.getItem("ticketholders")) {
    let ticketholders = JSON.parse(localStorage.getItem("ticketholders"));
    loadTicketHolders(ticketholders);
    loadTicketData(ticketholders[localStorage.getItem("ticketholder")]);
  }

  $("#expirydate").val(localStorage.getItem("expirydate"));
  $("#ticket").val(localStorage.getItem("ticket"));

  loadDepartures();
});

$("#closemodal").click(() => {
  $("#ticketholderdialog").removeAttr("open");
});

$("#newticketholder").click(() => {
  $("#holderdialogmode").val("save");
  $("#ticketholdertitle").text("Add ticket holder");
  $("#firstname").val("");
  $("#surname").val("");
  $("#streetaddress").val("");
  $("#postalcode").val("");
  $("#city").val("");
  $("#ssn").val("");
  $("#telno").val("");
  $("#email").val("");
  $("#submitholder").text("Add");

  $("#ticketholderdialog").attr("open", "true");
});

$("#openinfo").click(() => {
  $("#info").attr("open", "true");
});

$("#closeinfo").click(() => {
  $("#info").removeAttr("open");
});

$("#editticketholder").click(() => {
  let ticketholders = JSON.parse(localStorage.getItem("ticketholders"));
  let ticketholder = ticketholders[$("#ticketholder").val()];

  $("#holderdialogmode").val("edit");
  $("#ticketholdertitle").text("Edit ticket holder");
  $("#firstname").val(ticketholder.firstName);
  $("#surname").val(ticketholder.surName);
  $("#streetaddress").val(ticketholder.streetNameAndNumber);
  $("#postalcode").val(ticketholder.postalCode);
  $("#city").val(ticketholder.city);
  $("#ssn").val(ticketholder.identityNumber);
  $("#telno").val(ticketholder.mobileNumber);
  $("#email").val(ticketholder.email);
  $("#submitholder").text("Save");

  $("#ticketholderdialog").attr("open", "true");
});

$("#saveticket").click(function (e) {
  localStorage.setItem("ticketholder", $("#ticketholder").val());
  localStorage.setItem("ticket", $("#ticket").val());
  localStorage.setItem("expirydate", $("#expirydate").val());

  $("#ticketforminfo").attr("style", "color:green").text("Details saved"),
    e.preventDefault();
});

$("#ticketholderform").submit(function (e) {
  let ticketholders = {};

  if (localStorage.getItem("ticketholders")) {
    ticketholders = JSON.parse(localStorage.getItem("ticketholders"));
  }

  ticketholders[$("#firstname").val()] = {
    firstName: $("#firstname").val(),
    surName: $("#surname").val(),
    city: $("#city").val(),
    streetNameAndNumber: $("#streetaddress").val(),
    postalCode: $("#postalcode").val(),
    identityNumber: $("#ssn").val(),
    mobileNumber: $("#telno").val(),
    email: $("#email").val(),
  };

  localStorage.setItem("ticketholders", JSON.stringify(ticketholders));
  loadTicketHolders(ticketholders);
  $("#ticketholderdialog").removeAttr("open");

  e.preventDefault();
});

$("#paybackform").submit(function (e) {
  if (
    localStorage.getItem("expirydate") >
      new Date().toLocaleDateString("sv-SE") ||
    confirm(
      `The ticket expired on ${localStorage.getItem(
        "expirydate"
      )}! Do you want to submit anyway?`
    )
  ) {
    jsonData = {};
    const data = $(this).serializeArray();
    jQuery.each(data, function () {
      jsonData[this.name] = this.value || "";
    });

    jsonData["customer"] = JSON.parse(localStorage.getItem("ticketholders"))[
      localStorage.getItem("ticketholder")
    ];
    $.post({
      url: "/api/submit",
      contentType: "application/json",
      data: JSON.stringify(jsonData),
      beforeSend: () =>
        $("#result")
          .attr("style", "color:green")
          .attr("aria-busy", "true")
          .text(""),
      success: (data) => $("#result").attr("aria-busy", "false").text(data),
      error: () =>
        $("#result")
          .attr("aria-busy", "false")
          .attr("style", "color:red")
          .text("Request failed"),
    });
  }
  e.preventDefault();
});

$("#departureLocation").on("change", async (event) => {
  const departureStation = event.target.value;

  await $.get({
    url: `/api/arrival_stations/${departureStation}`,
    success: (response) => {
      $("#arrivalLocation").empty();
      $.each(response.stations, (i, val) => {
        $("#arrivalLocation").append(
          $("<option>", {
            value: val.name,
            text: val.longname,
          })
        );
      });
    },
  });

  await loadDepartures();
});

$("#departureDate").on("change", loadDepartures);

$("#arrivalLocation").on("change", loadDepartures);

function loadTicketData(th) {
  let expiryDate = localStorage.getItem("expirydate");

  if (expiryDate < new Date().toLocaleDateString("sv-SE")) {
    $("#ticketsummary").attr("style", "color:red");
    $("#ticketsummary").text(
      `Ticket (${th.firstName} ${th.surName}'s ticket - EXPIRED ${expiryDate})`
    );
  } else {
    $("#ticketsummary").text(
      `Ticket (${th.firstName} ${th.surName}'s ticket expiring ${expiryDate})`
    );
  }
}

function loadTicketHolders(thObj) {
  $("#ticketholder").html("");

  $.each(Object.keys(thObj), (i, key) => {
    $("#ticketholder").append(
      $("<option>", {
        value: thObj[key].firstName,
        text: `${thObj[key].firstName} ${thObj[key].surName}`,
      })
    );
  });
}

function loadDepartures() {
  $.get({
    url: `/api/departures/${$("#departureLocation").val()}/${$(
      "#arrivalLocation"
    ).val()}/${$("#departureDate").val()}`,
    dataType: "json",
    success: (response) => {
      $("#departures").empty();
      $.each(response, (i, val) => {
        $("#departures").append(
          $("<option>", {
            value: val.split("T")[1],
            text: val.split("T")[1],
          })
        );
      });
      $("#departures").val($("#departures option:last").val());
    },
    error: (e) => console.log(e),
  });
}

$("#autoSubmit").click(() => {
  // Read the auto date, start time, and Trafikverket API key inputs.
  let autoDate = $("#autoDate").val().trim();
  let startTime = $("#autoStartTime").val().trim();
  let tvApiKey = $("#tvApiKey").val().trim();

  // Cache the Trafikverket API key.
  if (tvApiKey) {
    localStorage.setItem("tv_api_key", tvApiKey);
  } else {
    tvApiKey = localStorage.getItem("tv_api_key") || "";
  }

  // Build the JSON payload.
  let jsonData = { 
    startTime: startTime,
    date: autoDate,
    tv_api_key: tvApiKey
  };

  if (localStorage.getItem("ticketholders") && localStorage.getItem("ticketholder")) {
    let ticketholders = JSON.parse(localStorage.getItem("ticketholders"));
    jsonData["customer"] = ticketholders[localStorage.getItem("ticketholder")];
  }

  $("#autoResult")
    .attr("aria-busy", "true")
    .text("Submitting...");

  $.ajax({
    type: "POST",
    url: "/api/auto_submit",
    contentType: "application/json",
    data: JSON.stringify(jsonData),
    success: (data) => {
      $("#autoResult").attr("aria-busy", "false").empty();
      if (data.status === "success" && data.found > 0) {
        $("#autoResult").text(data.message || "No result message found.");

        let listContainer = $('<div id=listDiv></div>');

        // Create a "Select All" checkbox
        let selectAllCheckbox = $('<input type="checkbox" id="selectAll">');
        let selectAllLabel = $('<label for="selectAll"> Select All</label>');
        listContainer.append(selectAllCheckbox).append(selectAllLabel);
        // Create a UL with id "submitList"
        let list = $("<ul></ul>").attr("id", "submitList");
      
        data.items.forEach((item, idx) => {
          // Each LI has the class "submitItem"
          let li = $("<li></li>").addClass("submitItem");
          let checkbox = $('<input type="checkbox" class="submission-item">').attr("data-index", idx);
        
          li.append(checkbox);
          li.append(` Train ${item.ticket} from ${item.from} to ${item.to} scheduled at ${item.departureTime} ${item.departureDate} was ${item.status}`);
          list.append(li);
        });
        listContainer.append(list)
        $("#autoResult").append(listContainer);
      
        // Add a button to submit selected items.
        let submitBtn = $('<button type="button" id="submitSelected">Submit selected</button>');
        $("#autoResult").append(submitBtn);
      
        // Event listener for "Select All" functionality
        selectAllCheckbox.on('click', function() {
          $('.submission-item').prop('checked', this.checked);
        });
      
        // If any individual checkbox is unchecked, uncheck the "Select All" checkbox
        $('.submission-item').on('click', function() {
          if (!$(this).prop('checked')) {
            selectAllCheckbox.prop('checked', false);
          } else if ($('.submission-item:checked').length === $('.submission-item').length) {
            selectAllCheckbox.prop('checked', true);
          }
        });
      } else {
        $("#autoResult").text(data.message || "No delays or cancellations found.");
      }
    },
    error: (err) => {
      $("#autoResult")
        .attr("aria-busy", "false")
        .attr("style", "color:red")
        .text("Request failed: " + err.responseText);
    }
  });
});

$("#autoResult").on("click", "#submitSelected", () => {
  let selectedItems = [];
  $(".submission-item:checked").each(function () {
    let index = $(this).data("index");
    selectedItems.push(autoItems[index]);
  });
  
  if (selectedItems.length === 0) {
    $("#autoResult").html("<p style='color:red;'>Please select at least one item to submit.</p>");
    return;
  }
  
  $.ajax({
    type: "POST",
    url: "/api/submit_selected",
    contentType: "application/json",
    data: JSON.stringify({ items: selectedItems }),
    success: (data) => {
      // Render the returned message in the #autoResult element.
      $("#autoResult").html("<p style='color:green;'>" + data.message + "</p>");
    },
    error: (err) => {
      $("#autoResult").html("<p style='color:red;'>Submission of selected items failed: " + err.responseText + "</p>");
    }
  });
});