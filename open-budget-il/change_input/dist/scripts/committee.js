var BASE_URL = 'http://localhost:3003/';

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
		list.find('li:last-child').focus();

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
	});

	$('.details_bottom').delegate('input','change', function(e) {
		var articleId = $(this).val();
		
		var row = $(this).parents('.transfer_row');
		var articleId = row.find("input[name='articleId']").val();
		var amount = row.find("input[name='amount']").val();
		var cond_amount = row.find("input[name='amount_conditional']").val();

		var requestCode = row.parents('.item').find("input[name='tableNum']").val();

		saveTransferData(requestCode, articleId, amount, cond_amount);
	});
});

function formatDate(ticks) {

	var t = parseInt(ticks);
	var date = new Date(t);		
	return date.getDate() + '.' + (date.getMonth() + 1) + '.' + date.getFullYear();
}

function addRow(listElm, data) {

	listElm.grow({
  		templateURL: 'dist/templates/li_transfer.html',
  		cache: true,
  		animation: 'slide',
  		speed: 50
	});

	listElm.grow('append', data);
}

function getEmptyTransfer(str) {
	return {id: null, articleId:'', amount:'', amount_conditional:''};
}

function populateItems(listElements, items) {
	listElements.grow({
		templateURL: 'dist/templates/li_transfer.html',
		cache: true,
		animation: 'slide',
		speed: 10
	});

	var len = items.length;
	for (var i = 0; i < len; i++) {		
		populateItem(items[i])
	}
}

function populateItem(item) {
	var id = item.pageId;
	var type = item.type || 2;
	var meta = item.meta || {};

	// TODO: populate hidden ID field and type select box
	var container = $(".item[data-id='" + id + "']");
	container.find('.request_table_select').val(type);

	if(type == 1) {
		// TODO: populate table numbers and date
	} else {	
		// TODO: populate table number
		var transfers = meta.transfers || [getEmptyTransfer()];
		var list = container.find('ul.transfers_list');		
		for (var j = 0; j < transfers.length; j++) {
			list.grow('append', transfers[j])
		};
	}
}

function addTableNum(listElm, data) {

	listElm.grow({
  		templateURL: 'dist/templates/li_tableNum.html',
  		cache: true,
  		animation: 'slide',
  		speed: 50
	});

	return listElm.grow('append', data);
}

function setArticleName(labelElm, name) {
	if (name)
		labelElm.removeClass('not_found').html(name);
	else
		labelElm.addClass('not_found').html('לא ידוע');
}

function getCommitteData() {
	var result = { 
		id: $('#committeeId').val(), 
		date: $('#committeeDate').val() 
	};
	return result;
}

function parseRequestCode(code) {
	var parts = code.split("-");
	var result = {
		leading_item: parts[0],
		req_code: parts[1]
	};
	return result;
}

function getYearByTicks(ticks) {
	var date = new Date(parseInt(ticks));
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
		'kind': type,
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

function saveTransferData(requestCodeStr, articleId, amount, conditionalAmount) {
	var committeeData = getCommitteData();
	var requestCode = parseRequestCode(requestCodeStr);

	var data = {
		'date': committeeData.date,
		'year': getYearByTicks(committeeData.date),
		'leading_item': requestCode.leading_item,
		'req_code': requestCode.req_code,
		'budget_code': fixArticleId(articleId),
		'net_expense_diff': amount,
		'gross_expense_diff': conditionalAmount
	};

	$.ajax({
  		url: BASE_URL + 'api/update/cl',
  		type:"POST",
  		data: JSON.stringify(data),
  		contentType:"application/json; charset=utf-8",
  		dataType:"json"
	});
}
