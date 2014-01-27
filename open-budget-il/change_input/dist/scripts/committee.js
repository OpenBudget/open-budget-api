var BASE_URL = '/';

$( document ).ready(function() {

	initPopop();

	$('#committeeHeader h4').text(formatDate($('#committeeDate').val()));

	$('#pagesCarousel .item').first().addClass('active');
	$('.carousel').carousel({
		interval: false
	});

        populateItems($('.details_bottom ul'), data );
	addTableNum($('.details_top .request_input ul'), { table_code: ''})

	$('.request_table_select').switchy();

	$('.switch_value.request_table').click(function(e) {
		var value = $(this).attr('data-value');
		$(this).parents('.switch_container').find('.request_table_select').val(value).change();
	});

	// DOM events
	$(document).keydown(function(e) {
			switch(e.which) {
        		case 37: // left
        			$('.carousel').carousel('prev');
        			break;
        		case 39: // right
        			$('.carousel').carousel('next');
        			break;
        		default: return;
    	}
    	e.preventDefault();
	});

	$('.request_table_select').change(function() {
		var type = $(this).val();
		var container = $(this).parents('.item ');
		container.toggleClass('table_view', type == 2);
	});

	$('.request_input').delegate('li:last-child input', 'change', function(e) {
		var list = $(this).parents('ul');
		addTableNum(list, {table_code: ''});
	        window.setTimeout( function() { list.find('li:last-child input').focus(); }, 100 );
	});

	$('.details_bottom ul').delegate('li .del_row', 'click', function(e) {
		var row = $(this).parents('li');
		row.animate({height:'toggle'}, 100, function() { row.remove(); });			
	});

	$('.details_bottom ul').delegate('.articleId input', 'change', function(e) {
		var txt = $(this);
		var articleId = txt.val();
		var articleTextElm = txt.parents('.transfer_row').find('.articleName');
		var date = getCommitteData().date;
		var year = getYearByTicks(date);

		$.ajax({
			url: BASE_URL + 'api/budget/' + fixArticleId(articleId) + "/" + year,
			dataType: 'jsonp',
			success: function(reponse) {
			    setArticleName(articleTextElm, reponse.title);
			    if (reponse.title && txt.parents('li').is(':last-child') && txt.val().length) 
				addRow(txt.parents('ul.transfers_list'), getEmptyTransfer());
     		},
     		error: function(){
         		setArticleName(articleTextElm, null);
     		}
 		});
	});

	$('.details_top').delegate('input','change', function(e) {
		var pageId = $(this).parents('.item').attr('data-id');
		var type = $(this).parents('.details_top').find('.request_table_select').val();		
		var requestCodes = [];
		
		var list = $(this).parents('.top_input').find('input');
		list.each(function(index, item) {
			value = $(item).val();
			if (value.length)
				requestCodes.push(value);
		});
		savePageData(pageId, type, requestCodes);
	        if ( type == 2 && requestCodes.length == 1) {
		    populateChanges(  $(this).parents('.item').find('ul.transfers_list') ,requestCodes[0] );
		}
	});

	$('.details_bottom').delegate('input','change', function(e) {
		

		var row = $(this).parents('.transfer_row');
	        var knownArticleId = row.find(".articleName[data-budget='OK']").length > 0;
	        var articleName = $.trim( row.find(".articleName").text() );
		var articleId = row.find("input[name='articleId']").val();
		var amount = row.find("input[name='amount']").val();
		var cond_amount = row.find("input[name='amount_conditional']").val();

		var requestCode = row.parents('.item').find("input[name='tableNum']").val();

	        if ( knownArticleId ) {
		    saveTransferData(requestCode, articleId, articleName, amount, cond_amount, row.find('.result-indicator'));
		}
	});

        $('img').click( function(e) {
	    rotate = $(this).attr("data-rotate");
	    rotate = parseInt(rotate);
	    rotate += 90;
	    rotate %= 360;
	    $(this).attr("data-rotate", rotate);
	} );
});

function formatDate(ticks) {

	var t = parseInt(ticks);
	var date = new Date(t);		
	return date.getDate() + '.' + (date.getMonth() + 1) + '.' + date.getFullYear();
}

function addRow(listElm, data) {

    var template = $('#template-li-transfer').html();
    var rendered = _.template(template, data);
    listElm.append(rendered);
}

function getEmptyTransfer(str) {
	return {id: null, articleId:'', amount:'', amount_conditional:'', articleName:''};
}

function populateChanges( list, req_code ) {
    var date = getCommitteData().date;
    var year = getYearByTicks(date);
    var template = $('#template-li-transfer').html();
    list.html(_.template(template,getEmptyTransfer()));

    $.ajax({
  	url: BASE_URL + 'api/changes/'+req_code+'/'+year,
  	dataType:"jsonp",
	success: function(transfers) {
	    var data = [];
	    for (var j = 0; j < transfers.length; j++) {
		data.push({
		    articleId: transfers[j].budget_code.substring(2),
		    articleName: transfers[j].budget_title,
		    amount: transfers[j].net_expense_diff,
		    amount_conditional: transfers[j].gross_expense_diff
		});
	    }
	    data = _.sortBy(data, function(x) { return x.articleId; });
	    data.push(getEmptyTransfer());
	    list.html('');
	    for (var j = 0; j < data.length; j++) {
		var rendered = _.template(template,data[j]);
		list.append(rendered);
	    }
	}
    });
}

function populateItems(listElements, items) {
    var len = items.length;
    for (var i = 0; i < len; i++) {		
	populateItem(items[i])
    }
}

function populateItem(item) {
	var id = item.pageId;
	var type = item.kind || 2;
	var meta = item.meta || {};
        var req_codes = item.req_ids || [];

	// TODO: populate hidden ID field and type select box
	var container = $(".item[data-id='" + id + "']");
        container.toggleClass('table_view', type == 2);
	container.find('.request_table_select').val(type);

	if(type == 1) {
	    var req_code_container = container.find('.request_input ul');
	    var template = $('#template-li-tableNum').html();
	    for ( var j = 0 ; j < req_codes.length ; j++ ) {
		var rendered = _.template(template,{table_code: req_codes[j]});
		req_code_container.append(rendered);
	    }
	} else {
	    if ( req_codes.length == 1 ) {
		var req_code = req_codes[0];
		container.find(".table_input input[name='tableNum']").val(req_code);
		populateChanges( container.find('ul.transfers_list'), req_code );
	    }
	}
}

function addTableNum(listElm, data) {

    var template = $('#template-li-tableNum').html();
    var rendered = _.template(template,data);
    
    return listElm.append(rendered);
}

function setArticleName(labelElm, name) {
	if (name) {
		labelElm.removeClass('not_found').html(name);
	        labelElm.attr("data-budget","OK");
	} else {
		labelElm.addClass('not_found').html('לא ידוע');
	        labelElm.attr("data-budget","");
        }
}

function getCommitteData() {
	var result = { 
		id: $('#committeeId').val(), 
		date: parseInt($('#committeeDate').val()) 
	};
	return result;
}

function parseRequestCode(code) {
	var parts = code.split("-");
	var result = {
		leading_item: parseInt(parts[0]),
		req_code: parseInt(parts[1])
	};
	return result;
}

function getYearByTicks(ticks) {
	var date = new Date(ticks);
	return date.getFullYear();
}

function fixArticleId(articleId) {
	var result = '';
	return articleId.length == 6 ? "00" + articleId : articleId;
}

function savePageData(pageId, type, requestCodes) {
	var committeeData = getCommitteData();
	var data = {
		'pdf': committeeData.id,
		'page': pageId,
		'kind': parseInt(type),
		'request_id': requestCodes
	};

	$.ajax({
  		url: BASE_URL + 'api/update/pcp',
  		type:"POST",
  		data: JSON.stringify(data),
  		contentType:"application/json; charset=utf-8",
  		dataType:"json"
	});
}

function saveTransferData(requestCodeStr, articleId, articleName, amount, conditionalAmount, resultElement) {
	var committeeData = getCommitteData();
	var requestCode = parseRequestCode(requestCodeStr);

	var data = {
		'date': committeeData.date,
		'year': getYearByTicks(committeeData.date),
		'leading_item': requestCode.leading_item,
		'req_code': requestCode.req_code,
		'budget_code': fixArticleId(articleId),
	        'budget_title': articleName,
		'net_expense_diff': parseInt(amount),
		'gross_expense_diff': parseInt(conditionalAmount)
	};
        resultElement.attr("class","result-indicator glyphicon glyphicon-cloud-upload");
	$.ajax({
  		url: BASE_URL + 'api/update/cl',
  		type:"POST",
  		data: JSON.stringify(data),
  		contentType:"application/json; charset=utf-8",
  		dataType:"text",
	        success: function() {
		    resultElement.attr("class","result-indicator glyphicon glyphicon-ok");
		},
	        error: function() {
		    resultElement.attr("class","result-indicator glyphicon glyphicon-remove");
		},
	});
}
