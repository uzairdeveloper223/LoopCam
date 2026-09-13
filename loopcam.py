#!/usr/bin/env python3
# purpose: route video and audio for virtual meetings and streaming
# name of app: loopcam
# author: uzair mughal
# github: github.com/uzairdeveloper223
# website: uzair.is-a.dev
# license: apache 2.0
# btw too many comments doesn't mean this is AI slop. it means i care about the next dev.

import os
import sys
import subprocess
import re
import signal

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
from gi.repository import Gtk, Gdk, GLib, GdkPixbuf

# ---------------------------------------------------------
# pulse audio manager (merged from rhythmroute)
# ---------------------------------------------------------
class PulseManager:
    def __init__(self):
        self.sink_name = "VirtualMic"
        self.source_name = "VirtualMicSource"
        self.loaded_modules = []
        self._real_speaker = None
        self._real_mic = None

        if not self.run_cmd(['pactl', '--version']):
            print("pactl not found. please install pulseaudio-utils.")
            sys.exit(1)

    def run_cmd(self, cmd, check=False, suppress_err=True):
        try:
            stderr_dest = subprocess.DEVNULL if suppress_err else subprocess.PIPE
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=stderr_dest, text=True, timeout=3, check=check)
            return result.stdout.strip()
        except Exception:
            return ""

    def get_default_device(self, dev_type="sink"):
        out = self.run_cmd(['pactl', f'get-default-{dev_type}'])
        if out: return out
        out = self.run_cmd(['pactl', 'info'])
        if out:
            search_str = "Default Sink:" if dev_type == "sink" else "Default Source:"
            for line in out.splitlines():
                if search_str in line:
                    return line.split(':', 1)[1].strip()
        return None

    def snapshot_real_devices(self):
        candidate_sink = self.get_default_device(dev_type="sink")
        candidate_source = self.get_default_device(dev_type="source")
        if candidate_sink and self.sink_name not in candidate_sink:
            self._real_speaker = candidate_sink
        if candidate_source and self.source_name not in candidate_source:
            self._real_mic = candidate_source

    def unload_all(self):
        self.restore_rhythmbox()
        if self._real_speaker:
            self.run_cmd(['pactl', 'set-default-sink', self._real_speaker])
        if self._real_mic:
            self.run_cmd(['pactl', 'set-default-source', self._real_mic])
        for mod_id in self.loaded_modules:
            self.run_cmd(['pactl', 'unload-module', mod_id])
        self.loaded_modules.clear()
        
        # fallback to clean up ghost modules that might have been left behind
        out = self.run_cmd(['pactl', 'list', 'modules', 'short'], suppress_err=False)
        if out:
            for line in out.splitlines():
                if self.sink_name in line or self.source_name in line or 'Virtual_Mic' in line:
                    parts = line.split()
                    if parts and parts[0].isdigit():
                        self.run_cmd(['pactl', 'unload-module', parts[0]])

    def setup_virtual_mic(self, mix_mode=False, hear_music=False):
        self.unload_all()
        self.snapshot_real_devices()
        if not self._real_speaker:
            return False, "could not detect your physical speakers. is a sound card available?"
        
        self.load_module('module-null-sink', [f'sink_name={self.sink_name}', 'sink_properties=device.description=Virtual_Mic_Sink'])
        self.load_module('module-virtual-source', [f'source_name={self.source_name}', f'master={self.sink_name}.monitor', 'source_properties=device.description=Virtual_Mic_Source'])
        self.run_cmd(['pactl', 'set-default-sink', self._real_speaker])
        
        if hear_music:
            self.load_module('module-loopback', [f'source={self.sink_name}.monitor', f'sink={self._real_speaker}', 'latency_msec=60', 'adjust_time=0'])
        if mix_mode:
            if not self._real_mic:
                return False, "could not detect a real microphone for mixing."
            self.load_module('module-loopback', [f'source={self._real_mic}', f'sink={self.sink_name}', 'latency_msec=50', 'adjust_time=0'])
        return True, "virtual mic setup complete."

    def load_module(self, name, args):
        cmd = ['pactl', 'load-module', name] + args
        out = self.run_cmd(cmd, suppress_err=False)
        if out and out.isdigit():
            self.loaded_modules.append(out)
            return out
        return None

    def get_rb_sink_input(self):
        out = self.run_cmd(['pactl', 'list', 'sink-inputs'])
        if not out: return None
        blocks = out.split('Sink Input #')
        for block in blocks[1:]:
            lines = block.splitlines()
            if not lines: continue
            idx = lines[0].strip()
            if 'application.name = "rhythmbox"' in block.lower():
                return idx
        return None

    def route_rhythmbox(self):
        rb_idx = self.get_rb_sink_input()
        if not rb_idx:
            return False, "rhythmbox audio stream not found. is a track playing?"
        out = self.run_cmd(['pactl', 'move-sink-input', rb_idx, self.sink_name], suppress_err=False)
        if out and "Failure" in out:
            return False, "failed to move rhythmbox stream."
        return True, "rhythmbox routed to virtual mic."

    def restore_rhythmbox(self):
        rb_idx = self.get_rb_sink_input()
        target_sink = self._real_speaker or self.get_default_device(dev_type="sink")
        if rb_idx and target_sink:
            self.run_cmd(['pactl', 'move-sink-input', rb_idx, target_sink])

# ---------------------------------------------------------
# rhythmbox mpris manager (merged from rhythmroute)
# ---------------------------------------------------------
class RhythmboxManager:
    def __init__(self):
        self.has_playerctl = bool(self.run_cmd(['playerctl', '--version']))
        self.dbus_dest = "org.mpris.MediaPlayer2.rhythmbox"
        self.dbus_path = "/org/mpris/MediaPlayer2"
        self.dbus_iface = "org.mpris.MediaPlayer2.Player"

    def run_cmd(self, cmd):
        try:
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, timeout=3)
            return result.stdout.strip()
        except Exception:
            return ""

    def is_running(self):
        out = self.run_cmd(['dbus-send', '--session', '--print-reply',
                      '--dest=org.freedesktop.DBus', '/org/freedesktop/DBus',
                      'org.freedesktop.DBus.ListNames'])
        return bool(out and self.dbus_dest in out)

    def command(self, cmd):
        if self.has_playerctl:
            p_cmd = 'play-pause' if cmd == 'PlayPause' else cmd.lower()
            self.run_cmd(['playerctl', '-p', 'rhythmbox', p_cmd])
        else:
            self.run_cmd(['dbus-send', '--session', '--type=method_call',
                     f'--dest={self.dbus_dest}', self.dbus_path, f'{self.dbus_iface}.{cmd}'])

    def _get_dbus_prop(self, prop):
        return self.run_cmd(['dbus-send', '--session', '--print-reply',
                        f'--dest={self.dbus_dest}', self.dbus_path,
                        'org.freedesktop.DBus.Properties.Get',
                        f'string:{self.dbus_iface}', f'string:{prop}'])

    def get_metadata(self):
        if not self.is_running():
            return ("Not Running", "---", "---")
        if self.has_playerctl:
            status = self.run_cmd(['playerctl', '-p', 'rhythmbox', 'status']) or "Stopped"
            title = self.run_cmd(['playerctl', '-p', 'rhythmbox', 'metadata', 'title']) or "Unknown Title"
            artist = self.run_cmd(['playerctl', '-p', 'rhythmbox', 'metadata', 'artist']) or "Unknown Artist"
            return (status, title, artist)
        
        status_out = self._get_dbus_prop('PlaybackStatus')
        status_match = re.search(r'string "(.*?)"', status_out)
        status = status_match.group(1) if status_match else "Stopped"
        
        meta_out = self._get_dbus_prop('Metadata')
        title_match = re.search(r'xesam:title.*?string "(.*?)"', meta_out, re.DOTALL)
        artist_match = re.search(r'xesam:artist.*?string "(.*?)"', meta_out, re.DOTALL)
        title = title_match.group(1) if title_match else "Unknown Title"
        artist = artist_match.group(1) if artist_match else "Unknown Artist"
        return (status, title, artist)

# ---------------------------------------------------------
# main gtk3 application
# ---------------------------------------------------------
class LoopCamApp(Gtk.Window):
    def __init__(self):
        super().__init__(title="LoopCam")
        self.set_default_size(600, 600)
        self.set_border_width(15)
        self.pulse = PulseManager()
        self.rb = RhythmboxManager()
        
        self.ffmpeg_proc = None
        self.is_paused = False
        
        # headerbar with 3-dots menu
        hb = Gtk.HeaderBar()
        hb.set_show_close_button(True)
        hb.props.title = "LoopCam"
        hb.props.subtitle = "Virtual Routing Suite"
        
        menu_button = Gtk.MenuButton()
        menu_button.set_image(Gtk.Image.new_from_icon_name("open-menu-symbolic", Gtk.IconSize.BUTTON))
        popover = Gtk.Popover()
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        vbox.set_border_width(10)
        about_btn = Gtk.ModelButton(text="About LoopCam")
        about_btn.connect("clicked", self.show_about_dialog)
        vbox.pack_start(about_btn, False, True, 0)
        quit_btn = Gtk.ModelButton(text="Quit")
        quit_btn.connect("clicked", lambda w: self.on_close(None))
        vbox.pack_start(quit_btn, False, True, 0)
        vbox.show_all()
        popover.add(vbox)
        menu_button.set_popover(popover)
        hb.pack_end(menu_button)
        self.set_titlebar(hb)

        self.notebook = Gtk.Notebook()
        self.add(self.notebook)

        self.build_camera_tab()
        self.build_audio_tab()
        
        self.connect("destroy", self.on_close)
        GLib.timeout_add_seconds(2, self.update_live_panel)

    def create_icon_button(self, icon_name, tooltip):
        btn = Gtk.Button()
        image = Gtk.Image.new_from_icon_name(icon_name, Gtk.IconSize.BUTTON)
        btn.set_image(image)
        btn.set_tooltip_text(tooltip)
        return btn

    def build_camera_tab(self):
        grid = Gtk.Grid(column_spacing=10, row_spacing=10)
        grid.set_margin_top(20)
        grid.set_margin_bottom(20)
        grid.set_margin_start(20)
        grid.set_margin_end(20)
        self.notebook.append_page(grid, Gtk.Label(label="Camera"))

        grid.attach(Gtk.Label(label="Camera Name:"), 0, 0, 1, 1)
        self.entry_name = Gtk.Entry(text="My Virtual Cam")
        grid.attach(self.entry_name, 1, 0, 2, 1)
        self.btn_unload = Gtk.Button(label="Unload Camera")
        self.btn_unload.connect("clicked", self.on_unload_camera)
        grid.attach(self.btn_unload, 3, 0, 1, 1)

        grid.attach(Gtk.Label(label="Video ID (10 is preferred):"), 0, 1, 1, 1)
        self.spin_id = Gtk.SpinButton()
        self.spin_id.set_range(0, 99)
        self.spin_id.set_value(10)
        grid.attach(self.spin_id, 1, 1, 1, 1)
        self.btn_load = Gtk.Button(label="Load Virtual Camera (pkexec)")
        self.btn_load.connect("clicked", self.on_load_camera)
        grid.attach(self.btn_load, 2, 1, 2, 1)

        grid.attach(Gtk.Label(label="Source Type:"), 0, 2, 1, 1)
        self.combo_source = Gtk.ComboBoxText()
        self.combo_source.append_text("Video File (Loop)")
        self.combo_source.append_text("IP Webcam URL")
        self.combo_source.append_text("OBS Virtual Output")
        self.combo_source.set_active(0)
        self.combo_source.connect("changed", self.on_source_changed)
        grid.attach(self.combo_source, 1, 2, 3, 1)

        self.source_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        self.file_chooser = Gtk.FileChooserButton(title="Select Video", action=Gtk.FileChooserAction.OPEN)
        self.source_box.pack_start(self.file_chooser, True, True, 0)
        self.entry_url = Gtk.Entry()
        self.entry_url.set_placeholder_text("https://192.168.1.5:8080/video")
        self.entry_url.set_no_show_all(True)
        self.source_box.pack_start(self.entry_url, True, True, 0)
        grid.attach(self.source_box, 0, 3, 4, 1)

        # global start and stop buttons
        self.btn_start = Gtk.Button(label="Start Streaming to Device")
        self.btn_start.connect("clicked", self.on_start_stream)
        self.btn_start.get_style_context().add_class("suggested-action")
        grid.attach(self.btn_start, 0, 4, 2, 1)

        self.btn_stop = Gtk.Button(label="Stop Stream")
        self.btn_stop.connect("clicked", self.on_stop_stream)
        self.btn_stop.get_style_context().add_class("destructive-action")
        grid.attach(self.btn_stop, 2, 4, 2, 1)

        # local video specific controls (simple posix signals)
        self.video_ctrl_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=15)
        self.video_ctrl_box.set_halign(Gtk.Align.CENTER)
        self.video_ctrl_box.set_margin_top(10)
        self.video_ctrl_box.set_no_show_all(True)
        
        self.btn_vid_play_pause = self.create_icon_button("media-playback-start-symbolic", "Play / Pause")
        self.btn_vid_play_pause.connect("clicked", self.on_vid_play_pause)
        self.video_ctrl_box.pack_start(self.btn_vid_play_pause, False, False, 0)
        
        self.btn_vid_restart = self.create_icon_button("view-refresh-symbolic", "Restart from beginning")
        self.btn_vid_restart.connect("clicked", self.on_vid_restart)
        self.video_ctrl_box.pack_start(self.btn_vid_restart, False, False, 0)

        self.lbl_vid_status = Gtk.Label(label="Status: Stopped")
        self.lbl_vid_status.get_style_context().add_class("dim-label")
        self.video_ctrl_box.pack_start(self.lbl_vid_status, False, False, 10)
        
        grid.attach(self.video_ctrl_box, 0, 5, 4, 1)

    def build_audio_tab(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        box.set_margin_top(20)
        box.set_margin_bottom(20)
        box.set_margin_start(20)
        box.set_margin_end(20)
        self.notebook.append_page(box, Gtk.Label(label="Audio (RhythmRoute)"))

        mode_frame = Gtk.Frame(label=" Routing Mode ")
        mode_grid = Gtk.Grid(column_spacing=10, row_spacing=5)
        mode_grid.set_margin_top(10)
        mode_grid.set_margin_bottom(10)
        mode_grid.set_margin_start(10)
        mode_grid.set_margin_end(10)
        
        self.radio_separate = Gtk.RadioButton.new_with_label_from_widget(None, "Music Only (Separate) - Friend hears only music")
        self.radio_mix = Gtk.RadioButton.new_with_label_from_widget(self.radio_separate, "Music + Microphone (Mix) - Friend hears you + music")
        self.check_hear = Gtk.CheckButton(label="Play music through my speakers too")
        self.check_hear.set_active(True)
        
        mode_grid.attach(self.radio_separate, 0, 0, 1, 1)
        mode_grid.attach(self.radio_mix, 0, 1, 1, 1)
        mode_grid.attach(self.check_hear, 0, 2, 1, 1)
        mode_frame.add(mode_grid)
        box.pack_start(mode_frame, False, False, 0)

        btn_box = Gtk.Box(spacing=10)
        self.btn_audio_connect = Gtk.Button(label="Setup & Connect")
        self.btn_audio_connect.get_style_context().add_class("suggested-action")
        self.btn_audio_connect.connect("clicked", self.do_audio_connect)
        
        self.btn_audio_disconnect = Gtk.Button(label="Restore Default")
        self.btn_audio_disconnect.get_style_context().add_class("destructive-action")
        self.btn_audio_disconnect.connect("clicked", self.do_audio_disconnect)
        
        btn_box.pack_start(self.btn_audio_connect, True, True, 0)
        btn_box.pack_start(self.btn_audio_disconnect, True, True, 0)
        box.pack_start(btn_box, False, False, 0)

        rb_frame = Gtk.Frame(label=" Live Rhythmbox Panel ")
        rb_grid = Gtk.Grid(column_spacing=10, row_spacing=5)
        rb_grid.set_margin_top(10)
        rb_grid.set_margin_bottom(10)
        rb_grid.set_margin_start(10)
        rb_grid.set_margin_end(10)
        
        self.lbl_rb_status = Gtk.Label(label="Status: Checking...", xalign=0)
        self.lbl_rb_track = Gtk.Label(label="Track: ---", xalign=0)
        self.lbl_rb_artist = Gtk.Label(label="Artist: ---", xalign=0)
        
        rb_grid.attach(self.lbl_rb_status, 0, 0, 3, 1)
        rb_grid.attach(self.lbl_rb_track, 0, 1, 3, 1)
        rb_grid.attach(self.lbl_rb_artist, 0, 2, 3, 1)
        
        ctrl_box = Gtk.Box(spacing=15)
        ctrl_box.set_halign(Gtk.Align.CENTER)
        ctrl_box.set_margin_top(10)
        
        btn_prev = self.create_icon_button("media-skip-backward-symbolic", "Previous Track")
        btn_prev.connect("clicked", lambda w: self.rb.command('Previous'))
        
        self.btn_play = self.create_icon_button("media-playback-start-symbolic", "Play / Pause")
        self.btn_play.connect("clicked", lambda w: self.rb.command('PlayPause'))
        
        btn_next = self.create_icon_button("media-skip-forward-symbolic", "Next Track")
        btn_next.connect("clicked", lambda w: self.rb.command('Next'))
        
        ctrl_box.pack_start(btn_prev, False, False, 0)
        ctrl_box.pack_start(self.btn_play, False, False, 0)
        ctrl_box.pack_start(btn_next, False, False, 0)
        
        rb_grid.attach(ctrl_box, 0, 3, 3, 1)
        rb_frame.add(rb_grid)
        box.pack_start(rb_frame, True, True, 0)

    def is_device_in_use(self, target):
        if self.ffmpeg_proc and self.ffmpeg_proc.poll() is None:
            return True
        try:
            res = subprocess.run(["fuser", target], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if res.returncode == 0: return True
        except FileNotFoundError:
            pass
        try:
            res = subprocess.run(["lsof", target], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if res.returncode == 0: return True
        except FileNotFoundError:
            pass
        return False

    def on_load_camera(self, widget):
        name = self.entry_name.get_text().replace(" ", "_")
        vid = int(self.spin_id.get_value())
        target = f"/dev/video{vid}"
        
        if os.path.exists(target):
            self.show_message("Notice", f"{target} already exists. it might already be loaded.")
            return

        cmd = ["pkexec", "modprobe", "v4l2loopback", f"exclusive_caps=1", f"card_label={name}", f"video_nr={vid}"]
        try:
            subprocess.run(cmd, check=True)
            self.show_message("Success", f"Loaded virtual camera at {target}")
        except subprocess.CalledProcessError:
            self.show_message("Error", "Failed to load module. did you enter your password correctly or is v4l2loopback installed?")

    def on_unload_camera(self, widget):
        self.on_stop_stream(widget)
        cmd = ["pkexec", "modprobe", "-r", "v4l2loopback"]
        try:
            subprocess.run(cmd, check=True)
            self.show_message("Success", "Virtual camera module unloaded.")
        except subprocess.CalledProcessError:
            self.show_message("Error", "Failed to unload. is it currently in use by an app like zoom, obs, or a browser? close those apps first.")

    def on_source_changed(self, combo):
        idx = combo.get_active()
        if idx == 0: # video file
            self.file_chooser.show()
            self.entry_url.hide()
            self.video_ctrl_box.show()
        else: # ip webcam or obs
            self.file_chooser.hide()
            if idx == 1: self.entry_url.show()
            else: self.entry_url.hide()
            self.video_ctrl_box.hide()

    def on_vid_play_pause(self, widget):
        # if ffmpeg is not running, start it
        if not self.ffmpeg_proc or self.ffmpeg_proc.poll() is not None:
            self.on_start_stream(widget)
            if self.ffmpeg_proc and self.ffmpeg_proc.poll() is None:
                self.btn_vid_play_pause.set_image(Gtk.Image.new_from_icon_name("media-playback-pause-symbolic", Gtk.IconSize.BUTTON))
                self.lbl_vid_status.set_text("Status: Playing")
                self.is_paused = False
        else:
            # toggle pause using posix signals. 
            # sigstop freezes the process exactly where it is. sigcont resumes it.
            if not self.is_paused:
                os.kill(self.ffmpeg_proc.pid, signal.SIGSTOP)
                self.btn_vid_play_pause.set_image(Gtk.Image.new_from_icon_name("media-playback-start-symbolic", Gtk.IconSize.BUTTON))
                self.lbl_vid_status.set_text("Status: Paused")
                self.is_paused = True
            else:
                os.kill(self.ffmpeg_proc.pid, signal.SIGCONT)
                self.btn_vid_play_pause.set_image(Gtk.Image.new_from_icon_name("media-playback-pause-symbolic", Gtk.IconSize.BUTTON))
                self.lbl_vid_status.set_text("Status: Playing")
                self.is_paused = False

    def on_vid_restart(self, widget):
        self.on_stop_stream(widget)
        # small delay to ensure the process is fully dead and device is released before restarting
        GLib.timeout_add(300, lambda: self.on_start_stream(None))

    def on_start_stream(self, widget):
        idx = self.combo_source.get_active()
        vid = int(self.spin_id.get_value())
        target = f"/dev/video{vid}"

        if not os.path.exists(target):
            self.show_message("Error", f"{target} does not exist. please load the virtual camera first.")
            return

        if self.is_device_in_use(target):
            self.show_message("Warning", f"{target} is currently in use by another process. stop it first or choose a different video id.")
            return

        if idx == 0: # video file
            uri = self.file_chooser.get_uri()
            if not uri:
                self.show_message("Notice", "Please select a video file first.")
                return
            path = uri.replace("file://", "")
            # simple, robust ffmpeg command. stream_loop -1 loops it infinitely.
            cmd = ["ffmpeg", "-re", "-stream_loop", "-1", "-i", path, "-vf", "scale=1280:720,format=yuv420p", "-f", "v4l2", "-vcodec", "rawvideo", target]
        
        elif idx == 1: # ip webcam
            url = self.entry_url.get_text()
            if not url.endswith("/video"):
                self.show_message("Notice", "The ip webcam url must end with /video")
                return
            cmd = ["ffmpeg", "-re", "-i", url, "-vf", "scale=1280:720,format=yuv420p", "-f", "v4l2", "-vcodec", "rawvideo", target]
            
        else: # obs output
            self.show_message("Info", "Please click 'Start Virtual Camera' inside obs studio now. loopcam will monitor the device.")
            return

        try:
            self.ffmpeg_proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.is_paused = False
            if idx == 0:
                self.btn_vid_play_pause.set_image(Gtk.Image.new_from_icon_name("media-playback-pause-symbolic", Gtk.IconSize.BUTTON))
                self.lbl_vid_status.set_text("Status: Playing")
            else:
                self.show_message("Streaming", f"Pushing video to {target}")
        except FileNotFoundError:
            self.show_message("Error", "ffmpeg is not installed. please install it to stream video.")

    def on_stop_stream(self, widget):
        if self.ffmpeg_proc and self.ffmpeg_proc.poll() is None:
            # if it's paused, we must resume it before terminating, otherwise it hangs
            if self.is_paused:
                os.kill(self.ffmpeg_proc.pid, signal.SIGCONT)
            self.ffmpeg_proc.terminate()
            self.ffmpeg_proc = None
            self.is_paused = False
            if hasattr(self, 'btn_vid_play_pause'):
                self.btn_vid_play_pause.set_image(Gtk.Image.new_from_icon_name("media-playback-start-symbolic", Gtk.IconSize.BUTTON))
                self.lbl_vid_status.set_text("Status: Stopped")

    def do_audio_connect(self, widget):
        if not self.rb.is_running():
            self.show_message("Notice", "Rhythmbox is not running.\nopen rhythmbox and start playing a track first.")
            return
            
        mix_mode = self.radio_mix.get_active()
        hear_music = self.check_hear.get_active()
        
        success, msg = self.pulse.setup_virtual_mic(mix_mode=mix_mode, hear_music=hear_music)
        if not success:
            self.show_message("Error", msg)
            return
            
        success, msg = self.pulse.route_rhythmbox()
        if not success:
            self.show_message("Warning", f"{msg}\nplease ensure a track is actively playing, then click setup again.")
            self.pulse.unload_all()
        else:
            self.show_message("Success", "Connected! set your voice app input to 'Virtual_Mic_Source'.")

    def do_audio_disconnect(self, widget):
        self.pulse.unload_all()
        self.show_message("Restored", "Disconnected. audio restored to default speakers.")

    def update_live_panel(self):
        status, title, artist = self.rb.get_metadata()
        
        if status == "Playing":
            stat_text = "Playing"
            if hasattr(self, 'btn_play'):
                self.btn_play.set_image(Gtk.Image.new_from_icon_name("media-playback-pause-symbolic", Gtk.IconSize.BUTTON))
                self.btn_play.set_tooltip_text("Pause Track")
        elif status == "Paused":
            stat_text = "Paused"
            if hasattr(self, 'btn_play'):
                self.btn_play.set_image(Gtk.Image.new_from_icon_name("media-playback-start-symbolic", Gtk.IconSize.BUTTON))
                self.btn_play.set_tooltip_text("Play Track")
        else:
            stat_text = status
            if hasattr(self, 'btn_play'):
                self.btn_play.set_image(Gtk.Image.new_from_icon_name("media-playback-start-symbolic", Gtk.IconSize.BUTTON))
                self.btn_play.set_tooltip_text("Play Track")
                
        self.lbl_rb_status.set_text(f"Status: {stat_text}")
        self.lbl_rb_track.set_text(f"Track: {title}")
        self.lbl_rb_artist.set_text(f"Artist: {artist}")
        
        return True

    def show_about_dialog(self, widget):
        dialog = Gtk.Dialog(transient_for=self, flags=0)
        dialog.set_default_size(350, 400)
        dialog.set_resizable(False)
        dialog.set_border_width(20)
        
        content_area = dialog.get_content_area()
        content_area.set_spacing(10)
        
        base_dir = os.path.dirname(os.path.abspath(__file__))
        logo_path = os.path.join(base_dir, "data", "loopcam.svg")
        
        if os.path.exists(logo_path):
            pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(logo_path, 96, 96)
            logo_img = Gtk.Image.new_from_pixbuf(pixbuf)
        else:
            logo_img = Gtk.Image.new_from_icon_name("camera-web", Gtk.IconSize.DIALOG)
            
        content_area.pack_start(logo_img, False, False, 0)
        
        name_lbl = Gtk.Label()
        name_lbl.set_markup("<span size='xx-large' weight='bold'>LoopCam</span>")
        name_lbl.set_margin_top(10)
        content_area.pack_start(name_lbl, False, False, 0)
        
        dev_lbl = Gtk.Label(label="Uzair Mughal")
        dev_lbl.set_margin_top(5)
        content_area.pack_start(dev_lbl, False, False, 0)
        
        ver_lbl = Gtk.Label(label="Version 1.0.0")
        ver_lbl.get_style_context().add_class("dim-label")
        content_area.pack_start(ver_lbl, False, False, 0)
        
        link_lbl = Gtk.Label()
        link_lbl.set_markup("<a href='https://uzair.is-a.dev'>uzair.is-a.dev</a>")
        link_lbl.set_margin_top(15)
        content_area.pack_start(link_lbl, False, False, 0)
        
        close_btn = Gtk.Button(label="Close")
        close_btn.connect("clicked", lambda w: dialog.destroy())
        close_btn.set_margin_top(20)
        close_btn.set_halign(Gtk.Align.CENTER)
        content_area.pack_start(close_btn, False, False, 0)
        
        dialog.show_all()
        dialog.run()
        dialog.destroy()

    def show_message(self, title, msg):
        dialog = Gtk.MessageDialog(transient_for=self, flags=0, message_type=Gtk.MessageType.INFO, buttons=Gtk.ButtonsType.OK, text=title)
        dialog.format_secondary_text(msg)
        dialog.run()
        dialog.destroy()

    def on_close(self, widget):
        self.on_stop_stream(None)
        self.pulse.unload_all()
        Gtk.main_quit()

if __name__ == "__main__":
    app = LoopCamApp()
    app.show_all()
    Gtk.main()