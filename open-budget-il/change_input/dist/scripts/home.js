function checkPDF(pdfId) {
    $.get("/api/pdf/"+pdfId, function(data) {
	pages = data.numPages;
	done = data.done;
	$("#message").html("מעבד את הקובץ... : "+pages+" דפים נמצאו");
	if ( done ) {
	    if ( pages > 0 ) {
		$("#submit-button").toggleClass("disabled", false);
	    } else {
		popup('לא נמצאו דפים בקובץ שהועלה', 'שגיאה');
	    }
	} 
    }, "json");
}

$( document ).ready(function() {
    
    initPopop();
    
    $('.datepicker').datepicker()
	.on('changeDate', function(e){
	    $(e.target).datepicker('hide');
	    var inputId = $(e.target).data('inputid');
	    $('#' + inputId).val(Date.parse(e.date));
	    $("#dropzone").css("visibility","visible");
	});
    
    $('#dropzone').filedrop({
	fallback_id: 'uploadBtn',    // an identifier of a standard file input element, becomes the target of "click" events on the dropzone
	url: uploadURL,              // upload handler, handles each file separately, can also be a function taking the file and returning a url
	paramname: 'file',   // POST parameter name used on serverside to reference file, can also be a function taking the filename and returning the paramname
	error: function(err, file) {
	    switch(err) {
            case 'BrowserNotSupported':
		popup('הדפדפן אינו תומך בגרירת קבצים', 'שגיאה')
		break;
            case 'TooManyFiles':
		popup('לא ניתן להעלות יותר מקובץ בודד', 'שגיאה')
		break;
            case 'FileExtensionNotAllowed':           
		popup('לא ניתן להעלות קבצים מסוג ' + file.name.split('.').pop(), 'שגיאה')
		break;
            case 'FileTooLarge':
		popup('הקובץ גדול מדי. גודל מרבי הינו 30 MB', 'שגיאה')
		break;
            default:
		popup('לא ניתן להעלות את הקובץ', 'שגיאה')
		break;
	    }
	},
	allowedfiletypes: [],   // filetypes allowed by Content-Type.  Empty array means no restrictions
	allowedfileextensions: ['.pdf'], // file extensions allowed. Empty array means no restrictions
	maxfiles: 1,
	maxfilesize: 30,    // max file size in MBs
	dragOver: function() {
            // user dragging files over #dropzone
	},
	dragLeave: function() {
            // user dragging files out of #dropzone
	},
	docOver: function() {
            // user dragging files anywhere inside the browser document window
	},
	docLeave: function() {
            // user dragging files out of the browser document window
	},
	drop: function() {
	},
	uploadStarted: function(i, file, len){
	    $("#message").html("טוען...");
	},
	uploadFinished: function(i, file, response, time) {
            if (response.success) {
		$('#requestFileUrl').val(response.id);
		$("#message").html("מעבד את הקובץ...");
		window.setInterval(checkPDF, 2000, response.id);
	    }
	},
	progressUpdated: function(i, file, progress) {
	},
	globalProgressUpdated: function(progress) {
	    $("#message").html("טוען... : "+progress+"%");
	},
	speedUpdated: function(i, file, speed) {
            // speed in kb/s
	},
	rename: function(name) {
	    return "upload.pdf";
            // name in string format
            // must return alternate name as string
	},
	beforeEach: function(file) {
            // file is a file object
            // return false to cancel upload
	},
	beforeSend: function(file, i, done) {
            // file is a file object
            // i is the file index
            done();
	},
	afterAll: function() {
            // runs after all files have been uploaded or otherwise dealt with
	}
    });
});
