// Démarrage de la SPA : déclaration des routes, chargement de la session, routeur.
import { setUnauthorizedHandler } from './api.js';
import { getUser, loadSession, setUser } from './auth.js';
import { albumPopup, artistPopup, playlistPopup, trackPopup } from './components/popups.js';
import { mountFullPage, mountInShell } from './components/shell.js';
import * as player from './player.js';
import { navigate, reset, route, start } from './router.js';
import { adminArtistsView } from './views/adminArtists.js';
import { adminFeaturedView } from './views/adminFeatured.js';
import { albumsView } from './views/albums.js';
import { artistAlbumsView } from './views/artistAlbums.js';
import { artistTracksView } from './views/artistTracks.js';
import { homeView } from './views/home.js';
import { likesView } from './views/likes.js';
import { loginView } from './views/login.js';
import { artistPendingView, artistRejectedView, notVerifiedView, verifyEmailView, verifyLinkView } from './views/messages.js';
import { newAlbumView } from './views/newAlbum.js';
import { forgotPasswordView, resetPasswordView } from './views/password.js';
import { playlistEditView } from './views/playlistEdit.js';
import { playlistsView } from './views/playlists.js';
import { profileView } from './views/profile.js';
import { registerArtistView, registerView } from './views/register.js';
import { searchView } from './views/search.js';

const full = (el) => mountFullPage(el);
const inShell = (nav) => (el) => mountInShell(el, nav);

// ---------- Authentification (pages sans coque) ----------
route('/login', { access: 'guest', render: loginView, mount: full });
route('/register', { access: 'guest', render: registerView, mount: full });
route('/register-artist', { access: 'guest', render: registerArtistView, mount: full });
route('/verify-email', { access: 'guest', render: verifyEmailView, mount: full });
route('/not-verified', { access: 'guest', render: notVerifiedView, mount: full });
route('/artist-pending', { access: 'guest', render: artistPendingView, mount: full });
route('/artist-rejected', { access: 'guest', render: artistRejectedView, mount: full });
route('/forgot-password', { access: 'guest', render: forgotPasswordView, mount: full });
route('/verify', { access: 'public', render: verifyLinkView, mount: full });
route('/reset-password', { access: 'public', render: resetPasswordView, mount: full });

// ---------- Espace User ----------
const USER = ['user'];
route('/home', { access: USER, render: homeView, mount: inShell('home') });
route('/likes', { access: USER, render: likesView, mount: inShell('likes') });
route('/albums', { access: USER, render: albumsView, mount: inShell('albums') });
route('/search', { access: USER, render: searchView, mount: inShell('search') });
route('/playlists', { access: USER, render: playlistsView, mount: inShell('playlists') });
route('/playlists/new', { access: USER, render: playlistEditView, mount: inShell('playlists') });
route('/playlists/:id/edit', { access: USER, render: playlistEditView, mount: inShell('playlists') });
route('/profile', { access: USER, render: profileView, mount: inShell('profile') });

// ---------- Espace Artist ----------
const ARTIST = ['artist'];
route('/artist/tracks', { access: ARTIST, render: artistTracksView, mount: inShell('tracks') });
route('/artist/albums', { access: ARTIST, render: artistAlbumsView, mount: inShell('albums') });
route('/artist/new-album', { access: ARTIST, render: newAlbumView, mount: inShell('new-album') });
route('/artist/profile', { access: ARTIST, render: profileView, mount: inShell('profile') });

// ---------- Espace Admin ----------
const ADMIN = ['admin'];
route('/admin/artists', { access: ADMIN, render: adminArtistsView, mount: inShell('artists') });
route('/admin/featured', { access: ADMIN, render: adminFeaturedView, mount: inShell('featured') });
route('/admin/profile', { access: ADMIN, render: profileView, mount: inShell('profile') });

// ---------- Pop-ups (une URL chacun) ----------
route('/track/:id', { access: ['user', 'artist'], popup: true, render: trackPopup });
route('/album/:id', { access: ['user', 'artist'], popup: true, render: albumPopup });
route('/artist/:id', { access: USER, popup: true, render: artistPopup });
route('/playlist/:id', { access: USER, popup: true, render: playlistPopup });

// Session expirée (refresh refusé) : retour à la connexion
setUnauthorizedHandler(() => {
  if (!getUser()) return;
  player.stop();
  setUser(null);
  reset();
  navigate('/login', { replace: true });
});

loadSession().then(start);
