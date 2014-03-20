
(function showPreviews() {
  // Show previews for post bodies in the dashboard
  var shower_links = document.querySelectorAll('.show-post-body');

  if (shower_links.length > 0) {
    Array.prototype.forEach.call(shower_links, function(link) {
      var target_id = link.getAttribute('href');
      window.link = link;
      var target_el = link.parentElement.querySelector(target_id);

      link.addEventListener('click', function(event) {
        event.preventDefault();
        link.classList.add('visuallyhidden');
        target_el.classList.remove('visuallyhidden');
      });
    });
  };
})();
