import requests
from bs4 import BeautifulSoup

def get_anime_recommendations(url):
    # Send a GET request to fetch the HTML content of the page
    response = requests.get(url)
    
    # Check if the request was successful
    if response.status_code != 200:
        print("Failed to retrieve the page")
        return []

    # Parse the page with BeautifulSoup
    soup = BeautifulSoup(response.content, 'lxml')

    # Find all anime recommendation items on the page
    recommendations = []

    # Each recommendation is inside a div with class "borderDark"
    for rec in soup.find_all('div', class_='borderDark'):
        title_tag = rec.find('a', class_='hoverinfo_trigger')
        if title_tag:
            title = title_tag.get_text(strip=True)
            url = title_tag['href']
            recommendations.append({'title': title, 'url': url})

    return recommendations

def display_recommendations(recommendations):
    # Display the top recommendations
    if not recommendations:
        print("No recommendations found.")
    else:
        print("Top Anime Recommendations:")
        for idx, rec in enumerate(recommendations, 1):
            print(f"{idx}. {rec['title']} - {rec['url']}")

if __name__ == "__main__":
    url = "https://myanimelist.net/recommendations.php?s=recentrecs&t=anime"
    recommendations = get_anime_recommendations(url)
    display_recommendations(recommendations)
