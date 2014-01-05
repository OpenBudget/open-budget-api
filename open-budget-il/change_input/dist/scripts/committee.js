$( document ).ready(function() {

	initPopop();

	$('#committeeHeader h4').text(formatDate($('#committeeHeader h4').text()));

	$('#pagesCarousel .item').first().addClass('active');
	$('.carousel').carousel({
		interval: false
	});

	populateItems($('.details_bottom ul'), data );

	$('.request_table_select').switchy();

	$('.switch_value.request_table').click(function(e) {
		var value = $(this).attr('data-value');
		$(this).parents('.switch_container').find('.request_table_select').val(value).change();
	});

	// DOM events
	$('.details_bottom .add_row').click(function(e) {
		var list = $(this).parents('.details_bottom').find('ul');
		addRow(list, getEmptyTransfer());
	});

	$('.details_bottom ul').delegate('li .del_row', 'click', function(e) {
		var row = $(this).parents('li');
		row.animate({height:'toggle'}, 100, function() { row.remove(); });			
	});

	$('.btns_container input[name="btnClear"]').click(function(e) {
		var container = $(this).parents('.details_bottom');
		container.find('input[type="text"]').val('');
		container.find("li.transfer_row:not(:first)").remove();		
	});

	$('.btns_container input[name="btnSave"]').click(function(e) {
		var container = $(this).parents('.item');
		var data = {
			pageId: container.find('.details_bottom').data('id'),
			pageNumber: container.find('input[name="tableNum"]').val(),
			image: container.find('.img_container img').attr('src'),
			transfers: []
		};
		
		$.each(container.find('li.transfer_row'), function(index, li) {
			var id = $(li).find('input[name="articleId"]').val();
			var transferAmount = $(li).find('input[name="amount"]').val();
			if (id && transferAmount)
				data.transfers.push({
					articleId: id,
					amount: transferAmount
			});
		});

		$.post( "page", data, function(result) {
  			if (result.success)
  				popup('המידע נשמר', 'הודעה');
		});
	});
});

function formatDate(ticks) {

	var t = parseInt(ticks);
	var date = new Date(t);		
	return date.getDate() + '.' + (date.getMonth() + 1) + '.' + date.getFullYear();
}

function addRow(listElm, data) {

	listElm.grow({
  		templateURL: 'templates/li_transfer.html',
  		cache: true,
  		animation: 'slide',
  		speed: 50
	});

	listElm.grow('append', data);
}

function getEmptyTransfer(str) {
	return {id: null, articleId:'', amount:''};
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
	var id = item.id;
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
		var list = container.find('ul');		
		for (var j = 0; j < transfers.length; j++) {
			list.grow('append', transfers[j])
		};
	}
}
