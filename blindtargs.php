<?php 
include "templates/header.php"; 
include "templates/headerclose.php"; 
?>

<h2> Blind Search Targets </h2>

<p>
These are depth of search results for the WFIRST CGI for blind search targets. Priority is based on the likelihood of CGI discovering a Neptune-sized planet or smaller about a given target (but should <strong>not</strong> be interpreted as a probability).  Click on the thumbnails to see the full-size depth of search static plot, and on the target name for an interactive version.
</p>


<?php 
$sql = "select * from BlindTargs order by Priority DESC";
?>    


<?php include("config.php"); ?>

<?php
$conn = new mysqli($servername, $username, $password, $dbname);
// Check connection
if ($conn->connect_error) {
    die("Connection failed: " . $conn->connect_error);
} 

echo "<h4>Query</h4><p>".$sql.";</p>\n\n";
$result = $conn->query($sql);
if ($result){
    if ($result->num_rows > 0) {
        echo "<h4>Result</h4><p>".$result->num_rows." rows returned.</p>\n\n";

        echo "<div class='results-outer'>\n";
        echo "<table class='results' id='gentable'><thead><tr>\n";
        echo "<th>Name</th><th>Priority</th><th>DoS</th>";
        echo "</tr></thead>\n";
        while($row = $result->fetch_assoc()) {
            echo "<tr><td>";
            echo "<a href='dosdetail.php?name=".urlencode($row["Name"])."'>".$row["Name"]."</a>";
            echo "</td><td>";
            echo $row["Priority"];
            echo "</td><td>";
            echo "<a href='DoSplots/".$row["Name"].".png'><img src='DoSplots/thumbs/".$row["Name"].".png'></a>";
            echo "</td></tr>";
        }
        echo "</table></div>\n";
    }
    $result->close();
} else{
    echo "Query Error:\n".$conn->error;
}
$conn->close();
?>


<?php include "templates/footer.php"; ?>

