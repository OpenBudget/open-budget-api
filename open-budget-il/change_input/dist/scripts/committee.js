var BUDGET_API_URL = 'http://the.open-budget.org.il/api/budget/';

$( document ).ready(function() {

	initPopop();

	$('#committeeHeader h4').text(formatDate($('#committeeHeader h4').text()));

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

		$.ajax({
			url: BUDGET_API_URL + articleId + "/2013",
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

	$('.item').delegate('input, select', 'change', function(e) {
		var id = $(this).parents('.item').attr('data-id');		
		// TODO: save transfer / page data
	});

	// $('.details_bottom .add_row').click(function(e) {
	// 	var list = $(this).parents('.details_bottom').find('ul');
	// 	addRow(list, getEmptyTransfer());
	// });

	// $('.btns_container input[name="btnClear"]').click(function(e) {
	// 	var container = $(this).parents('.details_bottom');
	// 	container.find('input[type="text"]').val('');
	// 	container.find("li.transfer_row:not(:first)").remove();		
	// });

	// $('.btns_container input[name="btnSave"]').click(function(e) {
	// 	var container = $(this).parents('.item');
	// 	var data = {
	// 		pageId: container.find('.details_bottom').data('id'),
	// 		pageNumber: container.find('input[name="tableNum"]').val(),
	// 		image: container.find('.img_container img').attr('src'),
	// 		transfers: []
	// 	};
		
	// 	$.each(container.find('li.transfer_row'), function(index, li) {
	// 		var id = $(li).find('input[name="articleId"]').val();
	// 		var transferAmount = $(li).find('input[name="amount"]').val();
	// 		if (id && transferAmount)
	// 			data.transfers.push({
	// 				articleId: id,
	// 				amount: transferAmount
	// 		});
	// 	});

	// 	$.post( "page", data, function(result) {
 //  			if (result.success)
 //  				popup('המידע נשמר', 'הודעה');
	// 	});
	// });
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
