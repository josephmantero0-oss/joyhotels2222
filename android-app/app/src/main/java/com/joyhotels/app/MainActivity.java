package com.joyhotels.app;

import android.Manifest;
import android.app.AlertDialog;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.graphics.Bitmap;
import android.graphics.Color;
import android.net.Uri;
import android.net.wifi.WifiInfo;
import android.net.wifi.WifiManager;
import android.os.Bundle;
import android.text.InputType;
import android.view.KeyEvent;
import android.view.View;
import android.view.Window;
import android.view.WindowManager;
import android.webkit.CookieManager;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Button;
import android.widget.EditText;
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.TextView;

import androidx.appcompat.app.AppCompatActivity;
import androidx.core.app.ActivityCompat;
import androidx.core.content.ContextCompat;
import androidx.swiperefreshlayout.widget.SwipeRefreshLayout;

import java.util.Locale;

public class MainActivity extends AppCompatActivity {

    private WebView webView;
    private ProgressBar progressBar;
    private LinearLayout errorLayout;
    private SwipeRefreshLayout swipeRefresh;
    private SharedPreferences prefs;

    private static final String PREFS_NAME = "JoyHotelsPrefs";
    private static final String KEY_SERVER_IP = "server_ip";
    private static final String KEY_SERVER_PORT = "server_port";
    private static final int FILE_CHOOSER_REQUEST = 1001;
    private static final int CAMERA_PERMISSION_REQUEST = 1002;
    private ValueCallback<Uri[]> fileUploadCallback;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        // Fullscreen immersive mode
        requestWindowFeature(Window.FEATURE_NO_TITLE);
        getWindow().setFlags(
            WindowManager.LayoutParams.FLAG_FULLSCREEN,
            WindowManager.LayoutParams.FLAG_FULLSCREEN
        );
        getWindow().setStatusBarColor(Color.parseColor("#10b981"));

        prefs = getSharedPreferences(PREFS_NAME, MODE_PRIVATE);

        // Build the UI programmatically (no XML dependency issues)
        buildUI();

        // Request camera permission for ID photo uploads
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.CAMERA)
                != PackageManager.PERMISSION_GRANTED) {
            ActivityCompat.requestPermissions(this,
                new String[]{Manifest.permission.CAMERA}, CAMERA_PERMISSION_REQUEST);
        }

        // Check if server IP is saved
        String savedIp = prefs.getString(KEY_SERVER_IP, null);
        if (savedIp == null || savedIp.isEmpty()) {
            showSetupDialog();
        } else {
            loadServer();
        }
    }

    private void buildUI() {
        // Root layout
        FrameLayout root = new FrameLayout(this);
        root.setBackgroundColor(Color.parseColor("#0f172a"));

        // Swipe-to-refresh wrapper
        swipeRefresh = new SwipeRefreshLayout(this);
        swipeRefresh.setColorSchemeColors(Color.parseColor("#10b981"));
        swipeRefresh.setOnRefreshListener(() -> {
            if (webView != null) webView.reload();
        });

        // WebView
        webView = new WebView(this);
        webView.setBackgroundColor(Color.parseColor("#0f172a"));
        setupWebView();
        swipeRefresh.addView(webView, new FrameLayout.LayoutParams(
            FrameLayout.LayoutParams.MATCH_PARENT,
            FrameLayout.LayoutParams.MATCH_PARENT
        ));

        root.addView(swipeRefresh, new FrameLayout.LayoutParams(
            FrameLayout.LayoutParams.MATCH_PARENT,
            FrameLayout.LayoutParams.MATCH_PARENT
        ));

        // Progress bar at top
        progressBar = new ProgressBar(this, null, android.R.attr.progressBarStyleHorizontal);
        progressBar.setMax(100);
        progressBar.setProgress(0);
        progressBar.setVisibility(View.GONE);
        FrameLayout.LayoutParams progressParams = new FrameLayout.LayoutParams(
            FrameLayout.LayoutParams.MATCH_PARENT, 6
        );
        progressBar.setProgressTintList(android.content.res.ColorStateList.valueOf(
            Color.parseColor("#10b981")));
        root.addView(progressBar, progressParams);

        // Error layout (hidden by default)
        errorLayout = new LinearLayout(this);
        errorLayout.setOrientation(LinearLayout.VERTICAL);
        errorLayout.setGravity(android.view.Gravity.CENTER);
        errorLayout.setBackgroundColor(Color.parseColor("#0f172a"));
        errorLayout.setVisibility(View.GONE);
        errorLayout.setPadding(60, 60, 60, 60);

        TextView errorIcon = new TextView(this);
        errorIcon.setText("📡");
        errorIcon.setTextSize(48);
        errorIcon.setGravity(android.view.Gravity.CENTER);
        errorLayout.addView(errorIcon);

        TextView errorTitle = new TextView(this);
        errorTitle.setText("Server Not Reachable");
        errorTitle.setTextColor(Color.WHITE);
        errorTitle.setTextSize(22);
        errorTitle.setGravity(android.view.Gravity.CENTER);
        LinearLayout.LayoutParams titleParams = new LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.WRAP_CONTENT, LinearLayout.LayoutParams.WRAP_CONTENT
        );
        titleParams.setMargins(0, 30, 0, 15);
        errorLayout.addView(errorTitle, titleParams);

        TextView errorMsg = new TextView(this);
        String ip = prefs.getString(KEY_SERVER_IP, "?");
        String port = prefs.getString(KEY_SERVER_PORT, "5000");
        errorMsg.setText("Cannot connect to " + ip + ":" + port +
            "\n\nMake sure:\n• Your PC server is running\n• Phone & PC are on the same Wi-Fi\n• The IP address is correct");
        errorMsg.setTextColor(Color.parseColor("#94a3b8"));
        errorMsg.setTextSize(14);
        errorMsg.setGravity(android.view.Gravity.CENTER);
        errorMsg.setLineSpacing(6, 1);
        errorLayout.addView(errorMsg);

        Button retryBtn = new Button(this);
        retryBtn.setText("🔄  Retry Connection");
        retryBtn.setTextColor(Color.WHITE);
        retryBtn.setBackgroundColor(Color.parseColor("#10b981"));
        retryBtn.setPadding(60, 30, 60, 30);
        retryBtn.setAllCaps(false);
        retryBtn.setTextSize(16);
        LinearLayout.LayoutParams retryParams = new LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.WRAP_CONTENT, LinearLayout.LayoutParams.WRAP_CONTENT
        );
        retryParams.setMargins(0, 50, 0, 20);
        retryBtn.setOnClickListener(v -> {
            errorLayout.setVisibility(View.GONE);
            webView.setVisibility(View.VISIBLE);
            loadServer();
        });
        errorLayout.addView(retryBtn, retryParams);

        Button changeIpBtn = new Button(this);
        changeIpBtn.setText("⚙️  Change Server IP");
        changeIpBtn.setTextColor(Color.parseColor("#94a3b8"));
        changeIpBtn.setBackgroundColor(Color.TRANSPARENT);
        changeIpBtn.setAllCaps(false);
        changeIpBtn.setTextSize(14);
        changeIpBtn.setOnClickListener(v -> showSetupDialog());
        errorLayout.addView(changeIpBtn);

        root.addView(errorLayout, new FrameLayout.LayoutParams(
            FrameLayout.LayoutParams.MATCH_PARENT,
            FrameLayout.LayoutParams.MATCH_PARENT
        ));

        setContentView(root);
    }

    private void setupWebView() {
        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setAllowFileAccess(true);
        settings.setAllowContentAccess(true);
        settings.setMediaPlaybackRequiresUserGesture(false);
        settings.setLoadWithOverviewMode(true);
        settings.setUseWideViewPort(true);
        settings.setBuiltInZoomControls(false);
        settings.setDisplayZoomControls(false);
        settings.setCacheMode(WebSettings.LOAD_DEFAULT);
        settings.setMixedContentMode(WebSettings.MIXED_CONTENT_ALWAYS_ALLOW);

        // Enable cookies for session persistence
        CookieManager cookieManager = CookieManager.getInstance();
        cookieManager.setAcceptCookie(true);
        cookieManager.setAcceptThirdPartyCookies(webView, true);

        webView.setWebViewClient(new WebViewClient() {
            @Override
            public void onPageStarted(WebView view, String url, Bitmap favicon) {
                progressBar.setVisibility(View.VISIBLE);
                errorLayout.setVisibility(View.GONE);
                webView.setVisibility(View.VISIBLE);
            }

            @Override
            public void onPageFinished(WebView view, String url) {
                progressBar.setVisibility(View.GONE);
                if (swipeRefresh.isRefreshing()) {
                    swipeRefresh.setRefreshing(false);
                }
            }

            @Override
            public void onReceivedError(WebView view, WebResourceRequest request,
                                        WebResourceError error) {
                // Only show error for main frame navigation failures
                if (request.isForMainFrame()) {
                    progressBar.setVisibility(View.GONE);
                    webView.setVisibility(View.GONE);
                    errorLayout.setVisibility(View.VISIBLE);
                    if (swipeRefresh.isRefreshing()) {
                        swipeRefresh.setRefreshing(false);
                    }
                }
            }
        });

        webView.setWebChromeClient(new WebChromeClient() {
            @Override
            public void onProgressChanged(WebView view, int newProgress) {
                progressBar.setProgress(newProgress);
                if (newProgress == 100) {
                    progressBar.setVisibility(View.GONE);
                }
            }

            // Handle file uploads (for ID photo, etc.)
            @Override
            public boolean onShowFileChooser(WebView webView, ValueCallback<Uri[]> callback,
                                             FileChooserParams params) {
                if (fileUploadCallback != null) {
                    fileUploadCallback.onReceiveValue(null);
                }
                fileUploadCallback = callback;

                Intent intent = params.createIntent();
                try {
                    startActivityForResult(intent, FILE_CHOOSER_REQUEST);
                } catch (Exception e) {
                    fileUploadCallback = null;
                    return false;
                }
                return true;
            }
        });
    }

    private void showSetupDialog() {
        AlertDialog.Builder builder = new AlertDialog.Builder(this);
        builder.setTitle("🖥️ Connect to JoyHotels Server");
        builder.setCancelable(false);

        LinearLayout layout = new LinearLayout(this);
        layout.setOrientation(LinearLayout.VERTICAL);
        layout.setPadding(50, 40, 50, 20);

        TextView infoText = new TextView(this);
        infoText.setText("Enter the IP address of the PC running JoyHotels.\n\n" +
            "You can find it by running 'ipconfig' on the PC and looking for 'IPv4 Address'.");
        infoText.setTextSize(13);
        infoText.setTextColor(Color.parseColor("#64748b"));
        layout.addView(infoText);

        // Detect current Wi-Fi network for hints
        try {
            WifiManager wifiManager = (WifiManager) getApplicationContext()
                .getSystemService(WIFI_SERVICE);
            WifiInfo wifiInfo = wifiManager.getConnectionInfo();
            String ssid = wifiInfo.getSSID();
            if (ssid != null && !ssid.equals("<unknown ssid>")) {
                TextView wifiText = new TextView(this);
                wifiText.setText("📶 Connected to: " + ssid);
                wifiText.setTextSize(12);
                wifiText.setTextColor(Color.parseColor("#10b981"));
                LinearLayout.LayoutParams wifiParams = new LinearLayout.LayoutParams(
                    LinearLayout.LayoutParams.WRAP_CONTENT,
                    LinearLayout.LayoutParams.WRAP_CONTENT
                );
                wifiParams.setMargins(0, 20, 0, 0);
                layout.addView(wifiText, wifiParams);
            }
        } catch (Exception e) {
            // ignore
        }

        // IP Address input
        TextView ipLabel = new TextView(this);
        ipLabel.setText("Server IP Address");
        ipLabel.setTextSize(14);
        LinearLayout.LayoutParams labelParams = new LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.WRAP_CONTENT, LinearLayout.LayoutParams.WRAP_CONTENT
        );
        labelParams.setMargins(0, 40, 0, 10);
        layout.addView(ipLabel, labelParams);

        EditText ipInput = new EditText(this);
        ipInput.setInputType(InputType.TYPE_CLASS_PHONE);
        ipInput.setHint("e.g. 192.168.1.8");
        String savedIp = prefs.getString(KEY_SERVER_IP, "192.168.1.8");
        ipInput.setText(savedIp);
        ipInput.setSelectAllOnFocus(true);
        layout.addView(ipInput);

        // Port input
        TextView portLabel = new TextView(this);
        portLabel.setText("Port (default: 5000)");
        portLabel.setTextSize(14);
        LinearLayout.LayoutParams portLabelParams = new LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.WRAP_CONTENT, LinearLayout.LayoutParams.WRAP_CONTENT
        );
        portLabelParams.setMargins(0, 20, 0, 10);
        layout.addView(portLabel, portLabelParams);

        EditText portInput = new EditText(this);
        portInput.setInputType(InputType.TYPE_CLASS_NUMBER);
        portInput.setHint("5000");
        String savedPort = prefs.getString(KEY_SERVER_PORT, "5000");
        portInput.setText(savedPort);
        layout.addView(portInput);

        builder.setView(layout);

        builder.setPositiveButton("Connect", (dialog, which) -> {
            String ip = ipInput.getText().toString().trim();
            String port = portInput.getText().toString().trim();
            if (ip.isEmpty()) ip = "192.168.1.8";
            if (port.isEmpty()) port = "5000";

            prefs.edit()
                .putString(KEY_SERVER_IP, ip)
                .putString(KEY_SERVER_PORT, port)
                .apply();

            loadServer();
        });

        builder.setNegativeButton("Cancel", null);
        builder.show();
    }

    private void loadServer() {
        String ip = prefs.getString(KEY_SERVER_IP, "192.168.1.8");
        String port = prefs.getString(KEY_SERVER_PORT, "5000");
        String url = String.format(Locale.US, "http://%s:%s", ip, port);
        webView.loadUrl(url);
    }

    private String getServerUrl() {
        String ip = prefs.getString(KEY_SERVER_IP, "192.168.1.8");
        String port = prefs.getString(KEY_SERVER_PORT, "5000");
        return String.format(Locale.US, "http://%s:%s", ip, port);
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode == FILE_CHOOSER_REQUEST) {
            if (fileUploadCallback != null) {
                Uri[] results = null;
                if (resultCode == RESULT_OK && data != null) {
                    String dataString = data.getDataString();
                    if (dataString != null) {
                        results = new Uri[]{Uri.parse(dataString)};
                    }
                }
                fileUploadCallback.onReceiveValue(results);
                fileUploadCallback = null;
            }
        }
    }

    // Handle Android back button — go back in WebView history first
    @Override
    public boolean onKeyDown(int keyCode, KeyEvent event) {
        if (keyCode == KeyEvent.KEYCODE_BACK) {
            if (webView.canGoBack()) {
                webView.goBack();
                return true;
            }
            // Long-press back to show settings
            if (event.isLongPress()) {
                showSetupDialog();
                return true;
            }
        }
        return super.onKeyDown(keyCode, event);
    }

    // Double-tap back to exit
    private long lastBackPress = 0;

    @Override
    public void onBackPressed() {
        if (webView.canGoBack()) {
            webView.goBack();
        } else {
            long now = System.currentTimeMillis();
            if (now - lastBackPress < 2000) {
                super.onBackPressed();
            } else {
                lastBackPress = now;
                android.widget.Toast.makeText(this,
                    "Press back again to exit. Hold back for settings.",
                    android.widget.Toast.LENGTH_SHORT).show();
            }
        }
    }
}
