/* Bank-transfer typeahead.
 *
 * A cosmetic aid for the demo: as the customer types a routing number or a
 * bank name, matches from the bundled directory drop down and a click fills
 * both the bank-name and routing-number fields. It is not a live ACH lookup
 * and validates nothing about a real account.
 *
 * Attach by giving an input class="bank-search-input" with:
 *   data-endpoint      URL of the JSON search endpoint
 *   data-fill-bank     id of the bank-name field to fill
 *   data-fill-routing  id of the routing-number field to fill
 */
(function () {
  'use strict';

  function debounce(fn, wait) {
    var t;
    return function () {
      var ctx = this, args = arguments;
      clearTimeout(t);
      t = setTimeout(function () { fn.apply(ctx, args); }, wait);
    };
  }

  function attach(input) {
    var endpoint = input.getAttribute('data-endpoint');
    if (!endpoint) return;

    var bankField = document.getElementById(input.getAttribute('data-fill-bank') || '');
    var routingField = document.getElementById(input.getAttribute('data-fill-routing') || '');

    input.setAttribute('autocomplete', 'off');
    var parent = input.parentNode;
    parent.style.position = 'relative';

    var menu = document.createElement('div');
    menu.className = 'bank-search-menu';
    menu.setAttribute('role', 'listbox');
    menu.hidden = true;
    parent.appendChild(menu);

    function close() { menu.hidden = true; menu.innerHTML = ''; }

    function choose(bank) {
      if (bankField) bankField.value = bank.name;
      if (routingField && bank.routing) routingField.value = bank.routing;
      close();
    }

    function render(results) {
      menu.innerHTML = '';
      if (!results.length) { close(); return; }
      results.forEach(function (bank) {
        var item = document.createElement('button');
        item.type = 'button';
        item.className = 'bank-search-item';
        item.setAttribute('role', 'option');
        var loc = [bank.city, bank.state].filter(Boolean).join(', ');
        item.innerHTML =
          '<span class="bank-search-name"></span>' +
          '<span class="bank-search-meta"></span>';
        item.querySelector('.bank-search-name').textContent = bank.name;
        item.querySelector('.bank-search-meta').textContent =
          bank.routing + (loc ? ' · ' + loc : '');
        item.addEventListener('mousedown', function (e) {
          e.preventDefault();          // keep focus off the blur handler
          choose(bank);
        });
        menu.appendChild(item);
      });
      menu.hidden = false;
    }

    var run = debounce(function () {
      var q = input.value.trim();
      if (q.length < 2) { close(); return; }
      fetch(endpoint + '?q=' + encodeURIComponent(q), {
        headers: { 'X-Requested-With': 'XMLHttpRequest' }
      })
        .then(function (r) { return r.ok ? r.json() : { results: [] }; })
        .then(function (data) { render(data.results || []); })
        .catch(function () { close(); });
    }, 200);

    input.addEventListener('input', run);
    input.addEventListener('focus', function () { if (input.value.trim().length >= 2) run(); });
    input.addEventListener('blur', function () { setTimeout(close, 150); });
  }

  document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('.bank-search-input').forEach(attach);
  });
})();
